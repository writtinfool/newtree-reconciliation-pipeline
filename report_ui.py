#!/usr/bin/env python3
"""Desktop UI for the single-property client report pipeline.

Run with (see also run_report_ui.bat, which pins the interpreter):
    python3 report_ui.py

Pick a CSV, optionally an output folder, check some boxes, hit Run. This
runs the same steps as run_client_reports.ps1 (reconcile.py + the three
report generators + optional PDF conversion) but drives them directly
via subprocess instead of shelling out to a second powershell.exe.

Why not just call run_client_reports.ps1? This machine has several
Python installs (some of them broken), and a freshly spawned
powershell.exe does its own independent PATH lookup for "python" --
which can land on a different, dependency-less interpreter than the one
actually running this GUI. Using sys.executable directly for reconcile.py
sidesteps that whole class of bug: whatever interpreter launched this
window is guaranteed to be the one reconcile.py runs under too.

run_client_reports.ps1 is still the source of truth for command-line /
scripted use -- this file intentionally mirrors its steps rather than
calling it, for the reliability reason above.

For the batch/prospecting use case (many properties from one export,
internal use, no client-facing polish) see the separate tool being
planned for that -- this UI is deliberately scoped to one property at a
time, matching run_client_reports.ps1 itself.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_COMPANY_NAME = "Newtree Capital Resources LLC"


def find_soffice():
    found = shutil.which("soffice")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


class StepFailed(Exception):
    pass


class ReportApp:
    def __init__(self, root):
        self.root = root
        root.title("Newtree Client Report Generator")
        root.geometry("760x520")

        self._build_form(root)
        self._build_log(root)

        self.running = False

    def _build_form(self, root):
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="x")

        ttk.Label(frame, text="Lead export CSV").grid(row=0, column=0, sticky="w")
        self.csv_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.csv_var, width=70).grid(row=1, column=0, columnspan=3, sticky="we")
        ttk.Button(frame, text="Browse...", command=self.on_browse_csv).grid(row=1, column=3, padx=(6, 0))

        ttk.Label(frame, text="Output folder (optional -- defaults to the CSV's own folder)").grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )
        self.outdir_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.outdir_var, width=70).grid(row=3, column=0, columnspan=3, sticky="we")
        ttk.Button(frame, text="Browse...", command=self.on_browse_outdir).grid(row=3, column=3, padx=(6, 0))

        ttk.Label(frame, text="Company name").grid(row=4, column=0, sticky="w", pady=(10, 0))
        self.company_var = tk.StringVar(value=DEFAULT_COMPANY_NAME)
        ttk.Entry(frame, textvariable=self.company_var, width=40).grid(row=5, column=0, columnspan=2, sticky="w")

        self.contact_info_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Include owner contact info in the reports", variable=self.contact_info_var
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.pdf_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text="Also generate PDFs (via LibreOffice)", variable=self.pdf_var
        ).grid(row=7, column=0, columnspan=3, sticky="w")

        button_row = ttk.Frame(frame)
        button_row.grid(row=8, column=0, columnspan=4, sticky="w", pady=(12, 0))
        self.run_button = ttk.Button(button_row, text="Run", command=self.on_run)
        self.run_button.pack(side="left")
        self.open_folder_button = ttk.Button(
            button_row, text="Open Output Folder", command=self.on_open_folder, state="disabled"
        )
        self.open_folder_button.pack(side="left", padx=(8, 0))

        frame.columnconfigure(0, weight=1)

    def _build_log(self, root):
        frame = ttk.Frame(root, padding=(10, 0, 10, 10))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Log").pack(anchor="w")
        self.log = scrolledtext.ScrolledText(frame, height=16, state="disabled", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _log_from_worker(self, text):
        self.root.after(0, self._append_log, text)

    def on_browse_csv(self):
        path = filedialog.askopenfilename(title="Select lead export CSV", filetypes=[("CSV files", "*.csv")])
        if path:
            self.csv_var.set(path)

    def on_browse_outdir(self):
        # Default to the CSV's own folder rather than an arbitrary OS location --
        # export folders are meant to be self-contained per deal, so that's almost
        # always where output belongs unless you're deliberately routing elsewhere.
        csv_path = self.csv_var.get().strip()
        initial_dir = os.path.dirname(csv_path) if csv_path and os.path.isfile(csv_path) else None
        path = filedialog.askdirectory(title="Select output folder", initialdir=initial_dir)
        if path:
            self.outdir_var.set(path)

    def on_open_folder(self):
        out_dir = self.outdir_var.get().strip() or os.path.dirname(self.csv_var.get().strip())
        if out_dir and os.path.isdir(out_dir):
            os.startfile(out_dir)

    def _run_step(self, args, cwd, step_name, allow_nonzero_if_missing=None):
        """Run one subprocess, streaming its output into the log.

        Raises StepFailed on nonzero exit, unless allow_nonzero_if_missing is a path
        that DOES exist despite the nonzero code -- used for build_collateral_summary.js,
        which exits 1 by design (not an error) when there's not enough data, and for
        that case only a nonzero exit AND a missing output file means real failure.
        """
        self._log_from_worker(f"\n$ {' '.join(str(a) for a in args)}\n")
        proc = subprocess.Popen(
            args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        for line in proc.stdout:
            self._log_from_worker(line)
        proc.wait()
        if proc.returncode != 0:
            if allow_nonzero_if_missing and not os.path.isfile(allow_nonzero_if_missing):
                self._log_from_worker(f"\n{step_name}: no output produced (insufficient data) -- see message above.\n")
                return
            if not allow_nonzero_if_missing:
                raise StepFailed(f"{step_name} failed (exit code {proc.returncode})")

    def on_run(self):
        if self.running:
            return

        csv_path = self.csv_var.get().strip()
        if not csv_path:
            messagebox.showwarning("Missing CSV", "Select a lead export CSV first.")
            return
        if not os.path.isfile(csv_path):
            messagebox.showerror("CSV not found", f"No such file:\n{csv_path}")
            return

        out_dir = self.outdir_var.get().strip() or os.path.dirname(csv_path)
        if not os.path.isdir(out_dir):
            messagebox.showerror("Output folder not found", f"No such folder:\n{out_dir}")
            return

        company_name = self.company_var.get().strip() or DEFAULT_COMPANY_NAME
        include_contact_info = self.contact_info_var.get()
        make_pdf = self.pdf_var.get()

        self.running = True
        self.run_button.config(state="disabled")
        self.open_folder_button.config(state="disabled")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._append_log(f"Python: {sys.executable}\nOutput folder: {out_dir}\n")

        def worker():
            try:
                node = shutil.which("node")
                if not node:
                    raise StepFailed("node not found on PATH")

                reconciled = os.path.join(out_dir, "reconciled.json")
                contact_args = ["--include-contact-info"] if include_contact_info else []

                self._run_step(
                    [sys.executable, "reconcile.py", "--csv", csv_path, "--out", reconciled],
                    REPO_ROOT, "reconcile.py",
                )

                docx_paths = []

                brief = os.path.join(out_dir, "01_Investment_Opportunity_Brief.docx")
                self._run_step(
                    [node, "generate_brief.js", reconciled, brief, company_name] + contact_args,
                    REPO_ROOT, "generate_brief.js",
                )
                docx_paths.append(brief)

                fact_sheet = os.path.join(out_dir, "02_Property_Fact_Sheet.docx")
                self._run_step(
                    [node, os.path.join("fact_sheet", "build_fact_sheet.js"), reconciled, fact_sheet, company_name] + contact_args,
                    REPO_ROOT, "build_fact_sheet.js",
                )
                docx_paths.append(fact_sheet)

                collateral = os.path.join(out_dir, "03_Loan_Collateral_Summary.docx")
                self._run_step(
                    [node, os.path.join("collateral_summary", "build_collateral_summary.js"), reconciled, collateral, company_name] + contact_args,
                    REPO_ROOT, "build_collateral_summary.js",
                    allow_nonzero_if_missing=collateral,
                )
                # Only produced when reconcile.py had enough data to compute collateral_analysis --
                # the generator exits without writing a file otherwise, so don't assume it's there.
                if os.path.isfile(collateral):
                    docx_paths.append(collateral)

                if make_pdf and docx_paths:
                    soffice = find_soffice()
                    if not soffice:
                        self._log_from_worker("\nLibreOffice (soffice) not found -- skipping PDF conversion.\n")
                    else:
                        # One invocation for all files, not one per file -- soffice --headless
                        # launches a background instance that locks its user profile, so firing
                        # it off repeatedly in a loop races on that lock and can silently no-op
                        # for all but the last file.
                        #
                        # Even a single invocation is flaky in practice -- soffice --headless has
                        # a known habit of intermittently failing (busy profile lock, slow startup)
                        # right after a previous conversion, so retry a couple of times.
                        expected_pdfs = [os.path.splitext(p)[0] + ".pdf" for p in docx_paths]
                        max_attempts = 3
                        for attempt in range(1, max_attempts + 1):
                            try:
                                self._run_step(
                                    [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir] + docx_paths,
                                    REPO_ROOT, "PDF conversion",
                                )
                            except StepFailed:
                                pass
                            if all(os.path.isfile(p) for p in expected_pdfs):
                                break
                            if attempt < max_attempts:
                                self._log_from_worker(
                                    f"\nPDF conversion attempt {attempt} of {max_attempts} didn't produce all files -- retrying...\n"
                                )
                                time.sleep(3)
                            else:
                                raise StepFailed(f"PDF conversion failed after {max_attempts} attempts")

                self.root.after(0, self._on_run_done, True, None)
            except StepFailed as e:
                self.root.after(0, self._on_run_done, False, str(e))
            except Exception as e:
                self.root.after(0, self._on_run_done, False, f"Unexpected error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_run_done(self, ok, error):
        self.running = False
        self.run_button.config(state="normal")
        if ok:
            self._append_log("\nDone.\n")
            self.open_folder_button.config(state="normal")
        else:
            self._append_log(f"\nFAILED: {error}\n")
            messagebox.showerror("Report generation failed", error)


if __name__ == "__main__":
    root = tk.Tk()
    ReportApp(root)
    root.mainloop()

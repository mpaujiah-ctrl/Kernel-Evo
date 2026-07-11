#!/usr/bin/env python3
"""
Fix: ksu_input_hook tidak terdefinisi saat KSU_KPROBES_HOOK aktif.

Root cause: di kernel/runtime/ksud_integration.c, variabel ksu_input_hook
cuma didefinisikan di dalam #else (mode non-kprobes), padahal dipakai
unconditional (tanpa #ifdef KSU_KPROBES_HOOK) di kernel/feature/selinux_hide.c.

Fix: cari baris "bool ksu_input_hook __read_mostly = true;" yang ada di
dalam blok #else, hapus dari situ, lalu sisipkan ulang setelah #endif
penutup blok tersebut supaya jadi unconditional. Line-based, whitespace-tolerant.
"""

import re
import sys

TARGET = "kernel/KernelSU-Next/kernel/runtime/ksud_integration.c"

LINE_PATTERN = re.compile(r"^\s*bool\s+ksu_input_hook\s+__read_mostly\s*=\s*true\s*;\s*$")
ENDIF_PATTERN = re.compile(r"^\s*#endif\b")
IFDEF_PATTERN = re.compile(r"^\s*#ifdef\s+KSU_KPROBES_HOOK\b")

def main():
    with open(TARGET, "r") as f:
        lines = f.readlines()

    target_idx = None
    for i, line in enumerate(lines):
        if LINE_PATTERN.match(line):
            target_idx = i
            break

    if target_idx is None:
        print("PERINGATAN: baris 'bool ksu_input_hook __read_mostly = true;' tidak ditemukan sama sekali.")
        print("Kemungkinan source berubah struktur total. Cek manual.")
        sys.exit(1)

    # Idempotent check: kalau baris tepat sebelumnya adalah #endif, berarti
    # ini hasil patch run sebelumnya (sudah unconditional) -> tidak perlu apa-apa.
    prev_line = lines[target_idx - 1] if target_idx > 0 else ""
    if ENDIF_PATTERN.match(prev_line):
        print("INFO: ksu_input_hook sudah unconditional (hasil patch sebelumnya). Tidak ada perubahan.")
        sys.exit(0)

    # Pastikan baris ini memang ada di dalam #ifdef KSU_KPROBES_HOOK ... #else ... #endif
    preceding = lines[max(0, target_idx - 15):target_idx]
    if not any(IFDEF_PATTERN.match(l) for l in preceding):
        print("PERINGATAN: baris ksu_input_hook ditemukan tapi konteksnya tidak dikenali (bukan hasil patch, bukan di dalam blok KSU_KPROBES_HOOK). Cek manual.")
        sys.exit(1)

    # Hapus baris ini dari posisi asalnya
    removed_line = lines.pop(target_idx)

    # Cari #endif pertama setelah titik penghapusan (menutup blok ifdef)
    endif_idx = None
    for i in range(target_idx, len(lines)):
        if ENDIF_PATTERN.match(lines[i]):
            endif_idx = i
            break

    if endif_idx is None:
        print("ERROR: tidak ketemu #endif setelah baris yang dihapus. Membatalkan, tidak menulis file.")
        sys.exit(1)

    # Sisipkan sebagai baris unconditional setelah #endif
    unconditional_line = "bool ksu_input_hook __read_mostly = true;\n"
    lines.insert(endif_idx + 1, unconditional_line)

    with open(TARGET, "w") as f:
        f.writelines(lines)

    print(f"Berhasil dipatch: baris dipindah dari posisi {target_idx + 1} ke setelah #endif (posisi {endif_idx + 2}).")

    # Verifikasi akhir (cek per baris, bukan whole-text, biar ^ / $ akurat)
    with open(TARGET, "r") as f:
        final_lines = f.readlines()
    count = sum(1 for l in final_lines if LINE_PATTERN.match(l))
    if count != 1:
        print(f"PERINGATAN: setelah patch, jumlah baris ksu_input_hook = {count} (harusnya 1). Cek manual!")
        sys.exit(1)

    print("Verifikasi OK: tepat 1 definisi ksu_input_hook, sekarang unconditional.")

if __name__ == "__main__":
    main()

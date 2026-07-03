#!/usr/bin/env python3
"""
inject_ksu_hooks.py

Inject hook manual KernelSU-Next ke titik-titik yang dibutuhkan buat
fungsi root beneran jalan (bukan cuma lolos Kbuild check reboot.c).

Dipanggil terpisah untuk tiap file:
    python3 inject_ksu_hooks.py exec       kernel/fs/exec.c
    python3 inject_ksu_hooks.py input      kernel/drivers/input/input.c
    python3 inject_ksu_hooks.py devpts     kernel/fs/devpts/inode.c

Kenapa pakai Python bukan sed multi-baris:
sed dengan insert multi-baris gampang meleset kalau ada perbedaan kecil
di source (indentasi, versi kernel, dst) - kalau pattern-nya gak ketemu
persis, sed diam-diam gak insert apa-apa tanpa error (persis kejadian
bug 'endmenu' sebelumnya). Python di sini melakukan exact string match
dan akan MENGGAGALKAN proses build (exit 1) kalau pattern tidak
ditemukan, jadi kalau source-nya beda struktur, ketahuan langsung
di CI - bukan baru ketahuan pas testing di HP.
"""

import sys
from pathlib import Path


def patch_exec(path: Path):
    marker = "ksu_handle_execveat"
    content = path.read_text()
    if marker in content:
        print("=== exec.c: hook sudah ada, skip ===")
        return

    # 1. extern declarations, sebelum definisi fungsi
    old_sig = (
        "static int do_execveat_common(int fd, struct filename *filename,\n"
        "\t\t\t      struct user_arg_ptr argv,\n"
        "\t\t\t      struct user_arg_ptr envp,\n"
        "\t\t\t      int flags)\n"
        "{\n"
        "\tchar *pathbuf = NULL;\n"
        "\tstruct linux_binprm *bprm;\n"
        "\tstruct file *file;\n"
        "\tstruct files_struct *displaced;\n"
        "\tint retval;\n"
        "\n"
        "\tif (IS_ERR(filename))"
    )
    if old_sig not in content:
        print("GAGAL: pattern do_execveat_common tidak ditemukan persis di exec.c")
        print("Cek manual, mungkin ada perbedaan whitespace/versi source.")
        sys.exit(1)

    extern_block = (
        "#ifdef CONFIG_KSU\n"
        "extern bool ksu_execveat_hook __read_mostly;\n"
        "extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr,\n"
        "\t\t\t\tvoid *argv, void *envp, int *flags);\n"
        "extern int ksu_handle_execveat_sucompat(int *fd, struct filename **filename_ptr,\n"
        "\t\t\t\t\tvoid *argv, void *envp, int *flags);\n"
        "#endif\n"
    )

    new_sig = (
        extern_block +
        "static int do_execveat_common(int fd, struct filename *filename,\n"
        "\t\t\t      struct user_arg_ptr argv,\n"
        "\t\t\t      struct user_arg_ptr envp,\n"
        "\t\t\t      int flags)\n"
        "{\n"
        "\tchar *pathbuf = NULL;\n"
        "\tstruct linux_binprm *bprm;\n"
        "\tstruct file *file;\n"
        "\tstruct files_struct *displaced;\n"
        "\tint retval;\n"
        "\n"
        "#ifdef CONFIG_KSU\n"
        "\tif (unlikely(ksu_execveat_hook))\n"
        "\t\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
        "\telse\n"
        "\t\tksu_handle_execveat_sucompat(&fd, &filename, &argv, &envp, &flags);\n"
        "#endif\n"
        "\n"
        "\tif (IS_ERR(filename))"
    )

    content = content.replace(old_sig, new_sig)
    path.write_text(content)
    print("=== exec.c: hook berhasil di-inject ===")


def patch_input(path: Path):
    marker = "ksu_handle_input_handle_event"
    content = path.read_text()
    if marker in content:
        print("=== input.c: hook sudah ada, skip ===")
        return

    old_sig = (
        "static void input_handle_event(struct input_dev *dev,\n"
        "\t\t\t       unsigned int type, unsigned int code, int value)\n"
        "{\n"
        "\tint disposition = input_get_disposition(dev, type, code, &value);\n"
        "\n"
        "\tif (disposition != INPUT_IGNORE_EVENT && type != EV_SYN)"
    )
    if old_sig not in content:
        print("GAGAL: pattern input_handle_event tidak ditemukan persis di input.c")
        sys.exit(1)

    extern_block = (
        "#ifdef CONFIG_KSU\n"
        "extern bool ksu_input_hook __read_mostly;\n"
        "extern int ksu_handle_input_handle_event(unsigned int *type, unsigned int *code,\n"
        "\t\t\t\t\t  int *value);\n"
        "#endif\n"
    )

    new_sig = (
        extern_block +
        "static void input_handle_event(struct input_dev *dev,\n"
        "\t\t\t       unsigned int type, unsigned int code, int value)\n"
        "{\n"
        "\tint disposition = input_get_disposition(dev, type, code, &value);\n"
        "\n"
        "#ifdef CONFIG_KSU\n"
        "\tif (unlikely(ksu_input_hook))\n"
        "\t\tksu_handle_input_handle_event(&type, &code, &value);\n"
        "#endif\n"
        "\n"
        "\tif (disposition != INPUT_IGNORE_EVENT && type != EV_SYN)"
    )

    content = content.replace(old_sig, new_sig)
    path.write_text(content)
    print("=== input.c: hook berhasil di-inject ===")


def patch_devpts(path: Path):
    marker = "ksu_handle_devpts"
    content = path.read_text()
    if marker in content:
        print("=== inode.c: hook sudah ada, skip ===")
        return

    old_sig = (
        "void *devpts_get_priv(struct dentry *dentry)\n"
        "{\n"
        "\tif (dentry->d_sb->s_magic != DEVPTS_SUPER_MAGIC)\n"
        "\t\treturn NULL;\n"
        "\treturn dentry->d_fsdata;\n"
        "}"
    )
    if old_sig not in content:
        print("GAGAL: pattern devpts_get_priv tidak ditemukan persis di inode.c")
        sys.exit(1)

    extern_block = (
        "#ifdef CONFIG_KSU\n"
        "extern int ksu_handle_devpts(struct inode *);\n"
        "#endif\n"
    )

    new_sig = (
        extern_block +
        "void *devpts_get_priv(struct dentry *dentry)\n"
        "{\n"
        "#ifdef CONFIG_KSU\n"
        "\tksu_handle_devpts(dentry->d_inode);\n"
        "#endif\n"
        "\tif (dentry->d_sb->s_magic != DEVPTS_SUPER_MAGIC)\n"
        "\t\treturn NULL;\n"
        "\treturn dentry->d_fsdata;\n"
        "}"
    )

    content = content.replace(old_sig, new_sig)
    path.write_text(content)
    print("=== inode.c: hook berhasil di-inject ===")


def main():
    if len(sys.argv) != 3:
        print("Usage: inject_ksu_hooks.py <exec|input|devpts> <path-to-file>")
        sys.exit(1)

    target, filepath = sys.argv[1], Path(sys.argv[2])
    if not filepath.exists():
        print(f"GAGAL: {filepath} tidak ditemukan")
        sys.exit(1)

    if target == "exec":
        patch_exec(filepath)
    elif target == "input":
        patch_input(filepath)
    elif target == "devpts":
        patch_devpts(filepath)
    else:
        print(f"GAGAL: target '{target}' belum didukung script ini")
        sys.exit(1)


if __name__ == "__main__":
    main()

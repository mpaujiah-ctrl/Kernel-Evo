import sys

with open('kernel/drivers/kernelsu/core_hook.c', 'r') as f:
    content = f.read()

if 'susfs.h' not in content:
    content = content.replace(
        '#include <linux/fs.h>',
        '#include <linux/fs.h>\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs.h>\n#endif',
        1
    )
    print("OK: include susfs.h ditambah")

content = content.replace(
    'void ksu_core_init(void)\n{',
    'void ksu_core_init(void)\n{\n#ifdef CONFIG_KSU_SUSFS\n\tsusfs_init();\n#endif'
)
print("OK: susfs_init ditambah ke ksu_core_init")

with open('kernel/drivers/kernelsu/core_hook.c', 'w') as f:
    f.write(content)

import sys

with open('kernel/drivers/kernelsu/core_hook.c', 'r') as f:
    content = f.read()

# Debug - cari semua fungsi void
import re
funcs = re.findall(r'void \w+\(void\)', content)
print("Fungsi void di core_hook.c:", funcs[:10])

if 'susfs_init' in content:
    print("susfs_init SUDAH ADA")
else:
    print("susfs_init BELUM ADA")

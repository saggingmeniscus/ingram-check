# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ingram-check standalone binary."""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['src/ingram_checker/__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'ingram_checker',
        'ingram_checker.checks',
        'ingram_checker.checks.barcode',
        'ingram_checker.checks.color',
        'ingram_checker.checks.content',
        'ingram_checker.checks.cover_size',
        'ingram_checker.checks.crop_marks',
        'ingram_checker.checks.fonts',
        'ingram_checker.checks.ink_density',
        'ingram_checker.checks.margins',
        'ingram_checker.checks.page_size',
        'ingram_checker.checks.pdfx',
        'ingram_checker.checks.resolution',
        'ingram_checker.fixers',
        'ingram_checker.fixers.color_converter',
        'ingram_checker.fixers.crop_stripper',
        'ingram_checker.fixers.icc_remover',
        'ingram_checker.fixers.image_resampler',
        'ingram_checker.fixers.page_padder',
        'ingram_checker.fixers.spot_converter',
        'pikepdf._core',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'xmlrpc',
        'pydoc',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ingram-check',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ingram-check',
)

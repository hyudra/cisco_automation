# -*- mode: python -*-

block_cipher = None

assetpath = os.path.dirname(os.path.abspath(SPEC))+'\\assets\\'
curpath = os.path.dirname(os.path.abspath(SPEC))
a = Analysis(['CiscoAuto.py'],
             pathex=[curpath],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
a.datas += 	[]
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='CiscoAuto',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True,
		  icon = assetpath + 'bredit.ico'		  )

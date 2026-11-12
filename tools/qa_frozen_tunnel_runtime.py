from pathlib import Path
import hashlib
import zipfile
root=Path(__file__).resolve().parents[1]/"evidence"/"qa"/"public-portable-prototype"
files=("base_library.zip","zlib1.dll","python314.dll")
for name in ("UniversalRemoteAgent-Preview","UniversalRemoteUpdater-Preview","UniversalRemoteTunnel-Preview"):
 print("=== ",name)
 for file in files:
  p=root/name/"_internal"/file
  with p.open("rb") as src: digest=hashlib.file_digest(src,"sha256").hexdigest()
  print(file,p.stat().st_size,digest)
  if file.endswith(".zip"):
   with zipfile.ZipFile(p) as z:
    print("zip integrity",z.testzip(), "encodings found",any(x.startswith("encodings/") for x in z.namelist()))

from ctypes import WinDLL
from audit_bundled_runtime import audit_one
for name in ("UniversalRemoteAgent-Preview","UniversalRemoteUpdater-Preview","UniversalRemoteTunnel-Preview"):
 package=root/name
 print("AUDIT",name)
 try:
  print(audit_one(package,name+".exe"))
 except Exception as e:print("AUDIT_ERROR",type(e).__name__,str(e)[:200])
 for dll in ("zlib1.dll","python314.dll"):
  try:print("WIN_DLL_LOAD",dll,WinDLL(str(package/"_internal"/dll))._handle)
  except OSError as ex:print("WIN_DLL_FAIL",dll,str(ex)[:250])
 z=package/"_internal"/"base_library.zip"
 with zipfile.ZipFile(z) as archive:
  entries=archive.namelist()
  for filename in ("encodings/__init__.pyc","encodings/utf_8.pyc","codecs.pyc"):
   if filename in entries:
    data=archive.read(filename)
    print("ZIP_ENTRY",filename,len(data),hashlib.sha256(data).hexdigest()[:15])
   else:print("ZIP_MISSING",filename)

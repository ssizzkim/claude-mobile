-- Excel 의 AppleScriptTask 가 부르는 연결 스크립트.
-- 설치 위치: ~/Library/Application Scripts/com.microsoft.Excel/banksort.scpt
on runBankSort(paths)
	return runPy("", paths)
end runBankSort

on targetNames(unused)
	return runPy("--target-names", "")
end targetNames

on runPy(flag, arg)
	set home to POSIX path of (path to home folder)
	set appDir to home & "Library/Application Support/BankSort/"
	set cmd to "export LANG=ko_KR.UTF-8 LC_ALL=ko_KR.UTF-8 PYTHONIOENCODING=utf-8; " & quoted form of (appDir & "venv/bin/python") & " " & quoted form of (appDir & "banksort.py")
	if flag is not "" then set cmd to cmd & " " & flag
	if arg is not "" then set cmd to cmd & " " & quoted form of arg
	try
		return do shell script cmd without altering line endings
	on error errMsg
		return "ERROR:" & errMsg
	end try
end runPy

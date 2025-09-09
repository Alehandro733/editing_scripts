@echo off
set "scriptDir=%~dp0"
type NUL > "%scriptDir%test.txt"
echo file "test.txt" created in %scriptDir%

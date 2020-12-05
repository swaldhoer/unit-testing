@REM SPDX-License-Identifier: MIT

@SET GOOGLETEST_REPOSITORY=https://github.com/google/googletest.git
@SET BUILD_DIRECTORY=build

@SET GIT_ROOT=%~dp0..
@CALL :NORMALIZEPATH %GIT_ROOT%
@SET GIT_ROOT=%NORMALIZEDPATH%
@ECHO Changing into "%GIT_ROOT%"
@PUSHD %GIT_ROOT%
@ECHO Cloning googletest from %GOOGLETEST_REPOSITORY%
@git clone %GOOGLETEST_REPOSITORY%
@PUSHD googletest
@ECHO Checking out commit "%1"
@git checkout %1
@ECHO Checking out commit "%1"
@ECHO Creating build directory "%BUILD_DIRECTORY%"
@MKDIR %BUILD_DIRECTORY%
@PUSHD %BUILD_DIRECTORY%
@cmake ..
@msbuild.exe googletest-distribution.sln /t:Build /p:Configuration=Debug /p:Platform=x64
@POPD
@POPD
@POPD

:NORMALIZEPATH
  @SET NORMALIZEDPATH=%~f1
  @EXIT /B

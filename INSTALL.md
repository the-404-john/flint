# Installing from Source

This document describes the requirements and steps necessary to build
the [Flint] interpreter into a high-performance standalone executable
using [Nuitka] **the** [Python] compiler.

> [!IMPORTANT]
> This document describes building [Flint] from source. This is not
> recommended if you don't know what you're doing. If you
> just want to run [Flint] right away, see the [Quick Start](#quick-start)
> section below.

[Flint]: https://github.com/the-404-john/flint
[Python]: https://www.python.org/
[Nuitka]: https://github.com/Nuitka/Nuitka#operating-system
[README.md]: https://github.com/the-404-john/flint/blob/main/README.md

Table of Contents
- [Quick Start](#quick-start)
- [Requirements](#requirements)
- [Build](#build)

## Quick Start

[Flint] has **zero external Python dependencies**. The interpreter runs
directly from source with any compatible [Python] installation — no
build step, no virtual environment, no package manager.

### 1. Clone the repository

```bash
git clone https://github.com/the-404-john/flint
cd flint
```

### 2. Lazy Run

```bash
python3 src/flint.py
```

That's it. To interpret a C file:

```bash
python3 src/flint.py hello.c
```

> [!NOTE]
> Python 3.10 or later is required. Check your version with
> `python3 --version`.

---

## Requirements

### Operating systems
Supported Operating Systems: [Linux], [FreeBSD], [NetBSD], [macOS]
and [Windows] (32 bits/64 bits/ARM).

[Linux]: https://github.com/torvalds/linux
[FreeBSD]: https://www.freebsd.org/
[NetBSD]: https://www.netbsd.org/
[macOS]: https://www.apple.com/os/macos/
[Windows]: https://www.microsoft.com/en-us/windows/

Other architectures are expected to also work out of the box. These
are just the ones tested and known to be good.

### Python
Need a [Python 3] (version 3.10 – 3.14) to build the project. Support
for new stable releases is added as they become available.

> [!NOTE]
> Ensure the pip and venv modules are also installed, as some package
> managers distribute them separately from the main [Python] package.

[Python 3]: https://docs.python.org/3/

### C Compiler
Need a C compiler with support for [C11].
- The [MinGW64] [C11] compiler, on [Windows].
- The [clang] compiler on [macOS] X and most [FreeBSD] architectures.
- On all other platforms, the [gcc] compiler of at least version 5.1.

[C11]: https://en.cppreference.com/w/c/11

[MinGW64]: https://www.mingw-w64.org/
[clang]: https://clang.llvm.org/
[gcc]: https://gcc.gnu.org/

### Git
Need [git] to clone the repository and manage the [source code].

[git]: https://git-scm.com/
[source code]: https://github.com/the-404-john/flint

## Build
### 1. Clone the [source code]
```bash
git clone https://github.com/the-404-john/flint
cd flint
```

### 2. Create a virtual environment
**[Linux]** | **[macOS]** | **[FreeBSD]** | **[NetBSD]**
```bash
python3 -m venv venv
source venv/bin/activate
```

**[Windows]**
```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install [Nuitka]

**[Linux]** | **[FreeBSD]** | **[NetBSD]**
```bash
pip install -U nuitka
pip install "patchelf>=0.17,<0.18"
```

> [!NOTE]
> `patchelf` is a Linux/BSD tool used by [Nuitka] to set shared-library
> RPATHs in the output binary. It is not needed on [macOS] or [Windows].

**[macOS]**
```bash
pip install -U nuitka
```

**[Windows]**
```cmd
pip install -U nuitka
```

### 4. Compile

All source files live under `src/`, so [Nuitka] must be invoked from
that directory.

**[Linux]** | **[macOS]** | **[FreeBSD]** | **[NetBSD]**
```bash
cd src
python3 -m nuitka \
    --onefile \
    --standalone \
    --lto=yes \
    --static-libpython=yes \
    --python-flag=-O \
    flint.py
```

**[Windows]**
```cmd
cd src
python -m nuitka ^
    --onefile ^
    --standalone ^
    --lto=yes ^
    --static-libpython=yes ^
    --python-flag=-O ^
    flint.py
```

The compiled binary will be placed in the `src/` directory.
| **Platform**                                | **Output File** |
|---------------------------------------------|-----------------|
| [Linux] \| [macOS] \| [FreeBSD] \| [NetBSD] | `flint.bin`     |
| [Windows]                                   | `flint.exe`     |

> [!NOTE]
> The resulting binary is fully self-contained. [Python] does not need
> to be installed on the target machine to run the
> [Flint] interpreter.

### 5. Install to `PATH`
**[Linux]** | **[FreeBSD]** | **[NetBSD]**
Copy the binary to `/usr/local/bin`, which is already on `PATH`
for all users.
```bash
sudo cp src/flint.bin /usr/local/bin/flint
sudo chmod +x /usr/local/bin/flint
```

Verify the installation:
```bash
which flint
flint --version
```

**[macOS]**
The [macOS] restricts unsigned binaries by default. Run the following
to remove the quarantine attribute before installing.
```bash
xattr -d com.apple.quarantine src/flint.bin
sudo cp src/flint.bin /usr/local/bin/flint
sudo chmod +x /usr/local/bin/flint
```

Verify the installation:
```bash
which flint
flint --version
```

**[Windows]**
Create a dedicated directory for local binaries, copy the executable,
and add the directory to your user `PATH` using PowerShell.
```powershell
mkdir "$env:USERPROFILE\bin"
copy src\flint.exe "$env:USERPROFILE\bin\flint.exe"
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
[Environment]::SetEnvironmentVariable("PATH", "$UserPath;$env:USERPROFILE\bin", "User")
```

> [!IMPORTANT]
> Changes to the `PATH` environment variable are written to the registry
> and only take effect in **new** terminal sessions.

Open a new terminal and verify the installation:
```cmd
where flint
flint --version
```

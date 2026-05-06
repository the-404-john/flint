python -m nuitka \
    --onefile \
    --standalone \
    --lto=yes \
    --static-libpython=yes \
    --python-flag=-O \
    --include-package-data=your_data_folder \
    main.py

something something make build stuff

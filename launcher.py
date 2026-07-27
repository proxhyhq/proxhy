# uv run pyinstaller --collect-submodules proxhy --collect-all numba --add-data assets:assets --name proxhy launcher.py

from proxhy.main import main

if __name__ == "__main__":
    main()

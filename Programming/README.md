# Using the Python environment

## Creating a Virtual Environment

Open PowerShell and navigate to your project folder:

Create a virtual environment (name = `RITvenv`):

```powershell
python -m venv RITvenv
```

This creates a folder called `RITvenv` containing an isolated Python installation.

## Activating the Environment

Now activate your environment:

```powershell
.\RITvenv\Scripts\Activate.ps1
```

You'll see `(RITvenv)` appear at the start of your command line, indicating you're inside the virtual environment.

## Deactivating the Environment

Simply type:

```powershell
deactivate
```

The `(RITvenv)` prefix will disappear.

## Installing Dependencies

While your environment is activated, install packages using pip:

```powershell
pip install pandas numpy requests
```

To see what's installed:

```powershell
pip list
```

## Saving Your Dependencies

Create a requirements file to track all installed packages:

```powershell
pip freeze > requirements.txt
```

This creates a `requirements.txt` file listing every package and its version.

## Moving to a New Device

On your new device, after creating and activating a fresh virtual environment, install all dependencies at once:

```powershell
pip install -r requirements.txt
```

This reads the `requirements.txt` file and installs everything exactly as it was on your original device.

## VSCode Integration

When you open your project in VSCode, it should automatically detect your virtual environment. You can also manually select it by pressing `Ctrl+Shift+P`, typing "Python: Select Interpreter", and choosing the one from your `RITvenv` folder (it'll show the path `.\SMIF\Scripts\python.exe`).

Once selected, VSCode's integrated terminal will automatically activate the virtual environment when you open a new terminal.

## **Quick Reference**

Here's the typical workflow:
1. Create: `python -m venv venv`
2. Activate: `.\venv\Scripts\Activate.ps1`
3. Install packages: `pip install package-name`
4. Save dependencies: `pip freeze > requirements.txt`
5. Deactivate: `deactivate`
6. On new device: create venv, activate it, then `pip install -r requirements.txt`

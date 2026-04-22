# Hot Wheels Timer

Desktop app for timing Hot Wheels races with ESP32 start/finish modules, a local car database, race history, and Google Sheets export.

## Current Version

- `1.2.6`

## Features

- connects to ESP32 start and finish modules
- measures race time and stores results locally
- keeps a car database in `cars.json`
- shows car posters from `car_images`
- exports and imports the car database in Excel format
- adds new cars from Excel and updates existing ones by `SKU`

## Main Files

- [timer_app.py](./timer_app.py) - main PyQt6 application
- [car_database.py](./car_database.py) - car database logic, Excel import/export, poster linking
- [dialogs.py](./dialogs.py) - dialogs for editing cars and settings
- [results_manager.py](./results_manager.py) - race results management
- [network_manager.py](./network_manager.py) - ESP32 communication
- [google_sheets.py](./google_sheets.py) - Google Sheets upload integration
- [cars.json](./cars.json) - local car database

## Excel Import/Export

The app exports the car database to `.xlsx` with two sheets:

- `Cars` - main import/export table
- `Reference` - helper lists for `Body`, `Type`, `Special`, and `Brand`

Expected column order on the `Cars` sheet:

`Name`, `Make`, `Model`, `Color`, `Weight (g)`, `SKU`, `Brand`, `Body`, `Type`, `Special`

Import behavior:

- new cars are added to the current database
- existing cars are updated only by `SKU`
- the database is not fully replaced during import
- a backup of `cars.json` is created before import
- `image` is filled automatically from `SKU`
- if no matching file is found, the default path becomes `car_images/<SKU>.webp`

## Posters

Car posters should be placed in the `car_images` folder.

Recommended naming:

- `SKU.webp`

Examples:

- `car_images/hry87.webp`
- `car_images/jjj52.webp`

## Running The App

Install dependencies and run:

```bash
python timer_app.py
```

## Building Windows EXE

Install PyInstaller once:

```powershell
python -m pip install pyinstaller
```

Then build the app:

```powershell
.\build_exe.ps1
```

The executable will be created here:

```text
dist\HotWheelsTimer\HotWheelsTimer.exe
```

Keep the whole `dist\HotWheelsTimer` folder together, because it contains the database, sounds, fonts, and car images used by the app.

## Notes

- `new cars.xlsx` is kept local and is not part of the repository
- Excel import expects the `Cars` sheet with the exported column structure

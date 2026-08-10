# Bluetooth Thermal Printers

The POS now includes an 80mm ESC/POS printer manager.

## Start the integrated POS

```bash
pip install -r requirements.txt
python run_pos.py
```

Open **Printers** → **Open Printer & Receipt Settings**.

### Discovery

- Live Bluetooth discovery is supported through `bleak` for BLE devices.
- Windows paired Bluetooth devices are also inspected through Windows Bluetooth/PnP information.
- Linux classic Bluetooth devices can be discovered through `bluetoothctl` when available.
- The printer screen displays discovered name, address/identifier, device type and details.

### Connect once / reconnect automatically

Select a printer, configure its RFCOMM channel (commonly `1` for classic Bluetooth SPP printers), then choose **Save & Connect**.

The selected printer is stored in `printer_config.json`. The POS attempts automatic reconnection at startup. On Windows, many Bluetooth thermal printers appear as a COM port after pairing; select/configure that COM port when required.

### Receipt themes

Built-in themes:

- Classic
- Compact
- Detailed

Themes can be edited and saved. Custom themes can be created and deleted. Available options include address, phone, cashier, invoice, footer text and item layout.

### Important hardware note

Bluetooth printers expose different protocols. The manager targets standard ESC/POS 80mm thermal printers. BLE-only printers that do not expose an ESC/POS print service may be discoverable but cannot necessarily be printed to without vendor-specific characteristics. Classic Bluetooth SPP/RFCOMM or a Windows virtual COM port is the most compatible setup.

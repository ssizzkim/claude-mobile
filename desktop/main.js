const { app, BrowserWindow, Menu, globalShortcut } = require('electron');
const path = require('path');

const PAGE = path.join(__dirname, 'renderer', 'index.html');

let mainWin = null;
let captureWin = null;

function createMainWindow() {
  if (mainWin && !mainWin.isDestroyed()) {
    mainWin.show();
    mainWin.focus();
    return;
  }
  mainWin = new BrowserWindow({
    width: 1140,
    height: 780,
    minWidth: 360,
    minHeight: 520,
    title: '조각',
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  mainWin.loadFile(PAGE);
  mainWin.on('closed', () => { mainWin = null; });
}

function openQuickCapture() {
  if (captureWin && !captureWin.isDestroyed()) {
    captureWin.show();
    captureWin.focus();
    return;
  }
  captureWin = new BrowserWindow({
    width: 560,
    height: 540,
    title: '조각 — 빠른 캡처',
    alwaysOnTop: true,
    fullscreenable: false,
    minimizable: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  captureWin.loadFile(PAGE, { hash: 'capture' });
  captureWin.on('closed', () => {
    captureWin = null;
    // main window shares the same localStorage; reload so the new card shows up
    if (mainWin && !mainWin.isDestroyed()) mainWin.webContents.reload();
  });
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', createMainWindow);

  app.whenReady().then(() => {
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      { role: 'appMenu' },
      {
        label: '파일',
        submenu: [
          { label: '빠른 캡처', accelerator: 'CommandOrControl+Shift+J', click: openQuickCapture },
          { type: 'separator' },
          { role: 'close', label: '창 닫기' },
        ],
      },
      { role: 'editMenu', label: '편집' },
      { role: 'windowMenu', label: '윈도우' },
    ]));

    createMainWindow();

    // Global quick capture — works from any app, even with no window open.
    globalShortcut.register('CommandOrControl+Shift+J', openQuickCapture);
  });

  app.on('activate', createMainWindow);

  app.on('window-all-closed', () => {
    // Stay alive on macOS so Cmd-Shift-J keeps working from other apps.
    if (process.platform !== 'darwin') app.quit();
  });

  app.on('will-quit', () => globalShortcut.unregisterAll());
}

/* global $, CSInterface, CSEvent, SystemPath */
(() => {
  'use strict';

  // ============================================================================
  // 1) Константы и интерфейсы
  // ============================================================================
  const EVENT_TYPE    = 'app.bridge.echo';
  const JSX_LOG_TYPE  = 'app.bridge.log';
  const REQ_PROC_TYPE = 'app.bridge.proc.run';
  const PPRO_TIMINGS_START = 'app.ppro.timings.start';
  const PPRO_TIMINGS_READY = 'app.ppro.timings.ready';

  // CSInterface
  const cs = new CSInterface();
  try { window.cs = cs; } catch (_) {}

  // Доступность Node.js
  const hasNode = (typeof require === 'function' && typeof process !== 'undefined');
  let cp = null;
  if (hasNode) {
    try { cp = require('child_process'); } catch (e) {}
  }

  // ============================================================================
  // 2) DOM / jQuery ссылки
  // ============================================================================
  const $el = (id) => $('#' + id);
  const $logJS   = $el('log-js');
  const $logJSX  = $el('log-jsx');
  const $msgJS   = $el('msg-js');
  const $btnSendJS  = $el('send-from-js');
  const $btnSendJSX = $el('send-from-jsx');
  const $pullState      = $el('pull-state');
  const $pushState      = $el('push-state');

  const $progExe        = $el('prog-exe');
  const $progExeBrowse  = $el('prog-exe-browse');
  const $progFile       = $el('prog-file');
  const $progFileBrowse = $el('prog-file-browse');
  const $progArgs       = $el('prog-args');
  const $progRun        = $el('prog-run');

  const $projectPath    = $el('project-path');
  const $projectBrowse  = $el('project-browse');
  const $languageCode   = $el('language-code');

  const $csvPath        = $el('csv-path');
  const $csvBrowse      = $el('csv-browse');
  
  const $audioPause     = $el('audio-pause');

  // ============================================================================
  // 3) Состояние
  // ============================================================================
  let cachedState = null;

  function readMyDataFromUI() {
    return {
      projectPath:  $.trim($projectPath.val() || ''),
      languageCode: $.trim($languageCode.val() || ''),
      csvPath:      $.trim($csvPath.val() || ''),
	    audioPause:   parseFloat($audioPause.val() || 0.5)
    };
  }

  function applyMyDataToUI(data) {
    if (!data || typeof data !== 'object') return;
    if (typeof data.projectPath  === 'string') $projectPath.val(data.projectPath);
    if (typeof data.languageCode === 'string') $languageCode.val(data.languageCode);
    if (typeof data.csvPath      === 'string') $csvPath.val(data.csvPath);
	  if (typeof data.audioPause   !== 'undefined') $audioPause.val(data.audioPause);
  }

  function saveMyDataToJsx() {
    const myData = readMyDataFromUI();
    const script = '($.global.CepJsxBridge && $.global.CepJsxBridge.exportState) ? $.global.CepJsxBridge.exportState() : "{}"';
    cs.evalScript(script, (ret) => {
      let st = {};
      try { st = ret ? JSON.parse(ret) : {}; } catch (_) { st = {}; }

      if (!st || typeof st !== 'object') st = {};
      if (!st.data || typeof st.data !== 'object') st.data = {};

      st.data.projectPath  = myData.projectPath;
      st.data.languageCode = myData.languageCode;
      st.data.csvPath      = myData.csvPath;
	    st.data.audioPause   = myData.audioPause; // Новое
	  
      cachedState = st;
      pushStateToJsx(st);
      logJS(`STATE merged & pushed: projectPath=${st.data.projectPath}, languageCode=${st.data.languageCode}, csvPath=${st.data.csvPath || ''}, audioPause=${st.data.audioPause}`);
    });
  }
    //дебаунс для защиты от быстрых запросов
    function debounce(fn, wait) {
    var t;
    return function() {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function() {
        fn.apply(ctx, args);
      }, wait);
    };
    }


  // ============================================================================
  // 4) Утилиты (логирование, сериализация, парсинг)
  // ============================================================================
  const now = () => { try { return new Date().toLocaleTimeString(); } catch (e) { return ''; } };

  const append = ($target, s) => {
    const t = $target.text();
    $target.text(t + '[' + now() + '] ' + s + '\n');
    const el = $target.get(0);
    if (el) el.scrollTop = el.scrollHeight;
  };
  const logJS   = (s) => append($logJS,  s);
  const logJSX  = (s) => append($logJSX, s);
  const logJSExec = (s) => logJS(s);

  const j = (str) => JSON.stringify(str);
  const parseData = (data) => { try { return JSON.parse(data); } catch (e) { return data; } };

  // ============================================================================
  // 5) PowerShell picker helper (Windows)
  // ============================================================================
  // Безопасная одинарная кавычка для PS
  function psQuote(s) { return "'" + String(s || '').replace(/'/g, "''") + "'"; }

  /**
   * Универсальный выбор пути через PowerShell (Windows, требует Node).
   * opts: { mode: 'folder'|'file', title?: string, startPath?: string, filter?: string }
   * filter пример: 'CSV files (*.csv)|*.csv|All files (*.*)|*.*'
   * cb(pathOrNull)
   */
  function pickPathPS(opts, cb) {
    if (!hasNode || !cp || process.platform !== 'win32') { cb(null); return; }
    opts = opts || {};
    var mode      = opts.mode || 'folder';
    var title     = opts.title || (mode === 'file' ? 'Выберите файл' : 'Выберите папку');
    var startPath = opts.startPath || '';
    var filter    = opts.filter || 'All files (*.*)|*.*';

    var parts = [
      "Add-Type -AssemblyName System.Windows.Forms",
      "$dlg = New-Object System.Windows.Forms.OpenFileDialog",
      "$dlg.Title = " + psQuote(title),
      startPath ? ("$dlg.InitialDirectory = " + psQuote(startPath)) : ""
    ];

    if (mode === 'folder') {
      parts.push(
        "$dlg.CheckFileExists = $false",
        "$dlg.ValidateNames  = $false",
        "$dlg.FileName = 'Select Folder'",
        "if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Split-Path -Parent $dlg.FileName }"
      );
    } else {
      parts.push(
        "$dlg.Filter = " + psQuote(filter),
        "$dlg.Multiselect = $false",
        "$dlg.CheckFileExists = $true",
        "$dlg.ValidateNames  = $true",
        "if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $dlg.FileName }"
      );
    }

    var ps = parts.filter(function (x) { return x && x.length; }).join("; ");

    cp.execFile(
      'powershell.exe',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps],
      { encoding: 'utf8', windowsHide: true },
      function (err, stdout /*, stderr */) {
        if (err) { cb(null); return; }
        var out = (stdout || '').trim();
        cb(out ? out.replace(/\\/g, '/') : null);
      }
    );
  }

  // ============================================================================
  // 6) CEP события: обработчики + подписки
  // ============================================================================
  const onEcho = (evt) => {
    const payload = parseData(evt.data);
    const txt  = (payload && payload.text) ? payload.text : String(payload);
    const from = (payload && payload.from) ? payload.from : '?';
    logJS('Получено событие ' + evt.type + ' (от: ' + from + '): ' + txt);
  };

  const onJsxLog = (evt) => logJSX(String(evt.data));

  // Универсальный запуск программы по событию из JSX
  function onProcRequest(evt) {
    const d = parseData(evt.data) || {};

    // Поддержка синонимов полей (на всякий случай)
    var program = '';
    if (d.program) program = String(d.program);
    else if (d.exe) program = String(d.exe);
    else if (d.interpreter) program = String(d.interpreter);
    else if (d.cmd) program = String(d.cmd);

    var filePath = null;
    if (typeof d.filePath === 'string' && d.filePath.length) filePath = d.filePath;
    else if (typeof d.file === 'string' && d.file.length)    filePath = d.file;
    else if (typeof d.script === 'string' && d.script.length) filePath = d.script;

    // argLine может прийти как строка или как массив args/argv
    var argLine = '';
    if (typeof d.argLine === 'string') {
      argLine = d.argLine;
    } else if (d.args && d.args.splice && typeof d.args.length === 'number') {
      argLine = joinArgsSafe(d.args);
    } else if (d.argv && d.argv.splice && typeof d.argv.length === 'number') {
      argLine = joinArgsSafe(d.argv);
    }

    if (!hasNode || !cp) return logJS('PROC: Node.js недоступен (проверьте манифест).');
    if (!program)        return logJS('PROC: не указана программа (program/exe).');

    // В runProgramExecFile 2-й и 3-й аргументы опциональны.
    // Передаём undefined, если они отсутствуют, чтобы логика "if (filePath) ..." сохранилась.
    runProgramExecFile(program, filePath || undefined, argLine || undefined).then((res) => {
      if (res.stdout) logJS(res.stdout.trim());
      if (res.stderr) logJS('ERR: ' + res.stderr.trim());
      logJS('PROC завершился с кодом: ' + res.code);
    }).catch((err) => logJS('PROC error: ' + (err && err.message ? err.message : String(err))));
  }

  function onPproTimingsStart(evt) {
  logJS('PPRO: старт сбора таймингов…'); // здесь можно задизейблить кнопки и т.п.
  }

  function onPproTimingsReady(evt) {
  const jsonPath = typeof evt.data === 'string' ? evt.data : (evt && evt.data && evt.data.path);
  logJS('PPRO: готов JSON таймингов: ' + (jsonPath || '(пусто)'));
  if (!jsonPath) return;

  try {
    const chosenCsv =
      $.trim($csvPath.val() || (cachedState && cachedState.data && cachedState.data.csvPath) || '');

    if (!chosenCsv) {
      logJS('⚠️ CSV не выбран. Укажите путь к CSV и повторите.');
      return;
    }

    const outPaths = srtBuildingModule.buildSrtFromJsonAndCsv(jsonPath, chosenCsv);

    if (Array.isArray(outPaths) && outPaths.length) {
      // Красивый вывод: нумерованный список путей
      const pretty = outPaths
        .map((p, i) => `${i + 1}. ${p}`)
        .join('\n');

      logJS('✅ SRT-файлы созданы (' + outPaths.length + '):\n' + pretty);
    } else {
      logJS('⚠️ Подходящие колонки не найдены или все пустые — SRT не создан.');
    }
  } catch (e) {
    logJS('❌ Ошибка сборки SRT: ' + (e && e.message ? e.message : e));
  }
}


  // Подписки
  cs.addEventListener(EVENT_TYPE,    onEcho);
  cs.addEventListener(JSX_LOG_TYPE,  onJsxLog);
  cs.addEventListener(REQ_PROC_TYPE, onProcRequest);
  cs.addEventListener(PPRO_TIMINGS_START, onPproTimingsStart);
  cs.addEventListener(PPRO_TIMINGS_READY, onPproTimingsReady);

  // ============================================================================
  // 7) Messaging API (JS ⇄ JSX события)
  // ============================================================================
  function dispatch(type, data) {
    const ev = new CSEvent(type, 'APPLICATION', cs.getApplicationID(), cs.getExtensionID());
    ev.data = (typeof data === 'string') ? data : JSON.stringify(data);
    cs.dispatchEvent(ev);
  }

  function sendFromJs(text) {
    const payload = { from: 'js', text: String(text), t: (new Date()).getTime() };
    dispatch(EVENT_TYPE, payload);
    logJS('Отправлено из JS: ' + payload.text);
  }

  function sendFromJsx(text) {
    cs.evalScript('$.global.CepJsxBridge && $.global.CepJsxBridge.sendMessage(' + j(String(text)) + ')');
  }

  // ============================================================================
  // 8) Синхронизация состояния с JSX
  // ============================================================================
  function pullStateFromJsx() {
    const script = '($.global.CepJsxBridge && $.global.CepJsxBridge.exportState) ? $.global.CepJsxBridge.exportState() : "{}"';
    cs.evalScript(script, (ret) => {
      try {
        cachedState = ret ? JSON.parse(ret) : {};
        const keys = Object.keys(cachedState || {});
        logJS('STATE pulled from JSX (' + (ret ? ret.length : 0) + ' chars). Keys: ' + (keys.length ? keys.join(', ') : '—'));
        applyMyDataToUI(cachedState && cachedState.data);
      } catch (e) {
        logJS('STATE pull parse error: ' + e + '; raw: ' + String(ret));
      }
    });
  }

  function pushStateToJsx(obj) {
    const json = JSON.stringify(obj || cachedState || {});
    const script = '$.global.CepJsxBridge && $.global.CepJsxBridge.importState(' + j(json) + ')';
    cs.evalScript(script, (ret) => logJSX('STATE pushed to JSX; result: ' + String(ret)));
  }

  // ============================================================================
  // 9) Node helpers
  // ============================================================================
  
  // Формат "HH:MM:SS,mmm"
  function formatSrtTime(sec) {
    const totalMs = Math.max(0, Math.round(Number(sec) * 1000));
    const ms = totalMs % 1000;
    const totalS = (totalMs - ms) / 1000;
    const s = totalS % 60;
    const totalM = (totalS - s) / 60;
    const m = totalM % 60;
    const h = (totalM - m) / 60;
    const pad2 = n => (n < 10 ? '0' : '') + n;
    const pad3 = n => (n < 10 ? '00' : (n < 100 ? '0' : '')) + n;
    return `${pad2(h)}:${pad2(m)}:${pad2(s)},${pad3(ms)}`;
  }

  // Простенький CSV-парсер
  function parseCSV(csvText) {
    if (!csvText) return { rows: [], headerMap: {} };
    csvText = csvText.replace(/^\uFEFF/, '');
    const firstLine = csvText.split(/\r?\n/)[0] || '';
    const cand = [',',';','\t','|'];
    let delim = ',';
    let bestCount = -1;
    for (let d of cand) {
      const cnt = (firstLine.match(new RegExp('\\' + d, 'g')) || []).length;
      if (cnt > bestCount) { bestCount = cnt; delim = d; }
    }
    const rows = [];
    let row = [];
    let field = '';
    let inQuotes = false;
    for (let i = 0; i < csvText.length; i++) {
      const ch = csvText[i];
      const next = csvText[i + 1];

      if (inQuotes) {
        if (ch === '"') {
          if (next === '"') { field += '"'; i++; }
          else { inQuotes = false; }
        } else { field += ch; }
      } else {
        if (ch === '"') {
          inQuotes = true;
        } else if (ch === delim) {
          row.push(field); field = '';
        } else if (ch === '\n') {
          row.push(field); field = '';
          rows.push(row); row = [];
        } else if (ch === '\r') {
          row.push(field); field = '';
          rows.push(row); row = [];
          if (next === '\n') { i++; }
        } else {
          field += ch;
        }
      }
    }
    if (field.length > 0 || row.length > 0) { row.push(field); rows.push(row); }

    const header = rows[0] || [];
    const headerMap = {};
    for (let i = 0; i < header.length; i++) { headerMap[String(header[i]).trim()] = i; }
    return { rows, headerMap };
  }

  // ============================================================================
  // 10) Разное: парсер аргументов, диалог выбора файла (CEP fallback)
  // ============================================================================
  function splitArgs(line) {
    if (!line) return [];
    const re = /"([^"]*)"|'([^']*)'|([^\s]+)/g;
    let m, out = [];
    while ((m = re.exec(line)) !== null) out.push(m[1] ?? (m[2] ?? m[3]));
    return out;
  }

  function joinArgsSafe(a) {
    try {
      var out = [];
      for (var i = 0; i < a.length; i++) {
        var s = a[i];
        if (s == null) continue;
        s = String(s);
        out.push(/\s|"/.test(s) ? '"' + s.replace(/"/g, '\\"') + '"' : s);
      }
      return out.join(' ');
    } catch (_) { return ''; }
  }

  function pickFileDialog(title, extsArr) {
    if (!window.cep || !cep.fs || typeof cep.fs.showOpenDialog !== 'function') { alert('cep.fs недоступен'); return null; }
    const res = cep.fs.showOpenDialog(false, false, title || 'Выберите файл', '', Array.isArray(extsArr) ? extsArr : []);
    return (res.err === cep.fs.NO_ERROR && res.data && res.data.length) ? res.data[0] : null;
  }

  // ============================================================================
  // 11) Универсальный запуск программы (execFile)
  // ============================================================================
  function runProgramExecFile(program, filePath, argLine) {
    return new Promise((resolve, reject) => {
      try {
        let exe = String(program || '').trim();
        if (!exe) return reject(new Error('Не указана программа (интерпретатор/исполняемый файл).'));

        const argsUser = splitArgs(String(argLine || ''));
        const argv = [];

        const name = exe.toLowerCase();
        if (name === 'cmd' || name === 'cmd.exe') {
          exe = process.env.comspec || 'cmd.exe';
          argv.push('/c');
          if (filePath) argv.push(String(filePath));
          argv.push(...argsUser);
        } else if (name === 'powershell' || name === 'powershell.exe') {
          exe = 'powershell.exe';
          argv.push('-NoProfile', '-ExecutionPolicy', 'Bypass');
          if (filePath) argv.push('-File', String(filePath));
          argv.push(...argsUser);
        } else {
          if (filePath) argv.push(String(filePath));
          argv.push(...argsUser);
        }

        const q = (s) => (/\s|"/.test(s) ? '"' + String(s).replace(/"/g, '\\"') + '"' : String(s));
        logJS('RUN: ' + q(exe) + ' ' + argv.map(q).join(' '));

        const opts = { windowsHide: true, encoding: 'utf8' };
        cp.execFile(exe, argv, opts, (err, stdout, stderr) => {
          if (err) return resolve({ code: err.code || -1, stdout: stdout || '', stderr: (stderr || err.message || '') });
          resolve({ code: 0, stdout: stdout || '', stderr: stderr || '' });
        });
      } catch (e) { reject(e); }
    });
  }

  // ============================================================================
  // 12) Привязка UI (автосейв на действия)
  // ============================================================================

  // Выбор ПАПКИ проекта через PowerShell
  $projectBrowse.on('click', function () {
    pickPathPS({
      mode: 'folder',
      title: 'Выберите папку проекта',
      startPath: $.trim($projectPath.val() || '')
    }, function (path) {
      if (!path) { logJS('Отмена выбора папки'); return; }
      $projectPath.val(path);
      saveMyDataToJsx();
      logJS('Node/PS pick (folder): ' + path);
    });
  });

  // Выбор CSV через PowerShell (только один файл)
  // Выбор CSV (и автоматическая установка projectPath в папку CSV)
// Выбор CSV (и автоматическая установка projectPath в папку CSV)
if ($csvBrowse && $csvBrowse.length) {
  $csvBrowse.on('click', function () {
    var start = $.trim($projectPath.val() || '');

    function handlePickedCsv(absPath) {
      var picked = (absPath || '').replace(/\\/g, '/');
      if (!picked) { logJS('Отмена выбора CSV'); return; }

      // Папка проекта = папка, где лежит CSV
      const path = require('path');
      var projDir = path.dirname(picked).replace(/\\/g, '/');

      $csvPath.val(picked);
      $projectPath.val(projDir);
      logJS('Project path установлен из CSV: ' + projDir);

      saveMyDataToJsx();
      logJS('Node/PS pick (csv): ' + picked);
    }

    pickPathPS({
      mode: 'file',
      title: 'Выберите CSV',
      startPath: start,
      filter: 'CSV files (*.csv)|*.csv|All files (*.*)|*.*'
    }, handlePickedCsv);
  });
}



  // Смена языка → сразу сохранить
  $languageCode.on('change', () => { saveMyDataToJsx(); });

  $audioPause.on('input change', debounce(saveMyDataToJsx, 500));

  function bindUI() {
    // Сообщения
    $btnSendJS.on('click', () => {
      const t = $.trim($msgJS.val()) || 'Привет из JS';
      sendFromJs(t);
    });
    $btnSendJSX.on('click', () => sendFromJsx('Привет из JSX'));

    // Синхронизация состояния
    $pullState.on('click', pullStateFromJsx);
    $pushState.on('click', () => pushStateToJsx());

    // Универсальный раннер
    $progExeBrowse.on('click', () => {
      const p = pickFileDialog('Выберите программу (exe/bat/cmd/ps1/py)', ['exe','bat','cmd','ps1','py']);
      if (p) $progExe.val(p);
    });

    $progFileBrowse.on('click', () => {
      const p = pickFileDialog('Выберите файл (.py/.ps1/.bat/.cmd/.exe)', ['py','ps1','bat','cmd','exe']);
      if (p) $progFile.val(p);
    });

    $progRun.on('click', () => {
      const program  = $.trim($progExe.val());
      const filePath = $.trim($progFile.val());
      const argLine  = String($progArgs.val() || '');
      if (!program) return alert('Укажите программу (python, powershell, cmd или путь к .exe)');

      runProgramExecFile(program, filePath, argLine).then((res) => {
        if (res.stdout) logJS(res.stdout.trim());
        if (res.stderr) logJS('ERR: ' + res.stderr.trim());
        logJS('PROC завершился с кодом: ' + res.code);
      }).catch((err) => logJS('PROC error: ' + (err && err.message ? err.message : String(err))));
    });
  }

 
// ============================================================================
// 12) SRT Builder Module (локальный объект, без глобалов)
// ============================================================================
const srtBuildingModule = (function(){
  const fs   = require('fs');
  const path = require('path');

  // ---------- ХЕЛПЕРЫ (инкапсулированы) ----------
  function sanitizeFilename(name) {
    return String(name)
      .replace(/[<>:"/\\|?*\x00-\x1F]/g, '_')
      .replace(/\.+$/,'')
      .trim() || 'column';
  }

  // SRT-текст из строк и таймингов (end[i] = start[i+1], у последнего — ends[i])
  function buildSrtText(lines, starts, ends) {
    const count = Math.min(starts.length, ends.length, lines.length);
    if (!count) return '';
    let srt = '';
    for (let i = 0; i < count; i++) {
      const startTime = starts[i];
      const endTime   = (i < count - 1) ? starts[i + 1] : ends[i];
      srt += (i + 1) + '\n'
          +  formatSrtTime(startTime) + ' --> ' + formatSrtTime(endTime) + '\n'
          +  lines[i] + '\n\n';
    }
    return srt;
  }

  function readAndValidateTimings(jsonPath) {
    if (!fs.existsSync(jsonPath)) throw new Error('JSON не найден: ' + jsonPath);
    const timings = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
    const starts = Array.isArray(timings.start) ? timings.start : [];
    const ends   = Array.isArray(timings.end)   ? timings.end   : [];
    if (!starts.length || !ends.length) throw new Error('В JSON пустые массивы start/end');
    if (starts.length !== ends.length) throw new Error('В JSON количество start не равно количеству end');
    return { starts, ends };
  }

  function readAndParseCsv(csvPath) {
    if (!fs.existsSync(csvPath)) throw new Error('CSV не найден: ' + csvPath);
    const csvRaw = fs.readFileSync(csvPath, 'utf8');
    const parsed = parseCSV(csvRaw); // используем ваш парсер из секции 9
    const rows = parsed && parsed.rows || [];
    const headerMap = parsed && parsed.headerMap || {};
    if (!rows.length) throw new Error('CSV пуст');
    const headerRow = rows[0] || [];
    return { rows, headerMap, headerRow };
  }

  function collectEligibleColumns(rows, headerMap, headerRow, bannedSet) {
    const cols = [];
    for (let c = 0; c < headerRow.length; c++) {
      const name = headerRow[c];
      if (name == null) continue;

      const displayName = String(name);
      const lc = displayName.toLowerCase().trim();
      if (!lc || bannedSet.has(lc)) continue;

      let idx = c;
      if (headerMap[displayName] !== undefined) idx = headerMap[displayName];

      const lines = [];
      for (let r = 1; r < rows.length; r++) {
        const cell = rows[r][idx];
        const txt = (cell == null ? '' : String(cell)).trim();
        if (txt) lines.push(txt);
      }
      cols.push({ name: displayName, index: idx, lines, nonEmptyCount: lines.length });
    }
    return cols;
  }

  function ensureColumnsPresenceOrThrow(eligibleCols) {
    if (!eligibleCols.length) {
      throw new Error('В CSV нет подходящих колонок (пустые заголовки или только из бан-листа).');
    }
  }

  function ensureAtLeastOneMatchesStartsOrThrow(eligibleCols, startsCount) {
    const ok = eligibleCols.some(col => col.nonEmptyCount === startsCount);
    if (!ok) {
      const csvNames = eligibleCols.map(c => c.name).join(', ');
      throw new Error(
        `Ни одна колонка из [${csvNames}] не имеет количество строк, равное ${startsCount} (количество аудио клипов).`
      );
    }
  }

  function writeFileSafe(absPath, content) {
    try { fs.writeFileSync(absPath, content, 'utf8'); return true; }
    catch (e) { if (console && console.warn) console.warn(`Не удалось записать файл "${absPath}": ${e.message}`); return false; }
  }

  function getExtensionTempPath() {
    const extRoot = cs.getSystemPath(SystemPath.EXTENSION);
    const outDir  = path.join(extRoot, 'temp');
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
    return outDir;
  }

  // ---------- ПУБЛИЧНЫЕ ФУНКЦИИ ----------
  /**
   * МНОГО: создаёт SRT-файлы для всех подходящих колонок рядом с CSV.
   * Нет требования «French». Нет базового файла в корне расширения.
   * Требует: starts.length === ends.length и хотя бы одна колонка с длиной == startsCount.
   * @returns {string[]} пути созданных файлов
   */
  function buildSrtFromJsonAndCsv(jsonPath, csvPath) {
    const { starts, ends } = readAndValidateTimings(jsonPath);
    const startsCount = starts.length;

    const { rows, headerMap, headerRow } = readAndParseCsv(csvPath);
    const bannedSet = new Set(['images', 'audio']);
    const eligibleCols = collectEligibleColumns(rows, headerMap, headerRow, bannedSet);

    ensureColumnsPresenceOrThrow(eligibleCols);
    ensureAtLeastOneMatchesStartsOrThrow(eligibleCols, startsCount);

    const csvDir = path.dirname(csvPath);
    const created = [];

    for (const col of eligibleCols) {
      const srtText = buildSrtText(col.lines, starts, ends);
      if (!srtText) continue;
      const safeName = sanitizeFilename(col.name) + '.srt';
      const outPath = path.join(csvDir, safeName);
      if (writeFileSafe(outPath, srtText)) created.push(outPath.replace(/\\/g, '/'));
    }
    return created;
  }

  /**
   * ОДИН: создаёт SRT по заданной колонке в <EXT>/temp/subtitles.srt.
   * Требует присутствия колонки и точного совпадения длины с startsCount.
   * @returns {string} путь к файлу
   */
  function buildSingleSrtFromJsonAndCsvInsideExtention(jsonPath, csvPath, targetCsvTitle) {
    if (targetCsvTitle == null || String(targetCsvTitle).trim() === '') {
      throw new Error('Не задан targetCsvTitle');
    }
    const targetName = String(targetCsvTitle);

    const { starts, ends } = readAndValidateTimings(jsonPath);
    const startsCount = starts.length;

    const { rows, headerMap, headerRow } = readAndParseCsv(csvPath);
    let colIndex = undefined;
    if (headerMap[targetName] !== undefined) colIndex = headerMap[targetName];
    else {
      const pos = headerRow.findIndex(h => String(h) === targetName);
      if (pos !== -1) colIndex = pos;
    }
    if (colIndex === undefined) throw new Error(`В CSV нет колонки "${targetName}"`);

    const lines = [];
    for (let r = 1; r < rows.length; r++) {
      const cell = rows[r][colIndex];
      const txt = (cell == null ? '' : String(cell)).trim();
      if (txt) lines.push(txt);
    }
    if (lines.length !== startsCount) {
      throw new Error(`Колонка "${targetName}" имеет ${lines.length} непустых строк, что не равно ${startsCount} (количество аудио клипов).`);
    }

    const srt = buildSrtText(lines, starts, ends);
    if (!srt) throw new Error(`Нет пересечения данных: timings/CSV ("${targetName}")`);

    const outDir  = getExtensionTempPath();
    const outPath = path.join(outDir, 'subtitles.srt');
    if (!writeFileSafe(outPath, srt)) throw new Error('Не удалось записать итоговый SRT: ' + outPath);
    return outPath.replace(/\\/g, '/');
  }

  // Возвращаем публичный API, хелперы остаются внутри
  return {
    buildSrtFromJsonAndCsv,
    buildSingleSrtFromJsonAndCsvInsideExtention
  };
})();


  // ============================================================================
  // 13) Bootstrap / Инициализация
  // ============================================================================
  function bootstrapJSX() {
    try {
      var dir   = cs.getSystemPath(SystemPath.EXTENSION).replace(/\\/g, '/') + '/jsx';
      var files = ['CepJsxBridge.jsx', 'tstScripts.jsx'];

      var es =
        '(function(d,f){' +
        '  for(var i=0;i<f.length;i++){' +
        '    try{$.evalFile(File(d+\"/\"+f[i]));}catch(e){}' +
        '  }' +
        '  return \"ok\";' +
        '})(' + JSON.stringify(dir) + ',' + JSON.stringify(files) + ');';

      cs.evalScript(es, function(){ logJSX("[bootstrap] ok"); });
    } catch (e) {
      logJSX('bootstrap error: ' + e);
    }
  }

  // === Инициализация ===
  function init() {
    bindUI();
    if (window.Editors && typeof window.Editors.setupEditors === 'function') {
      window.Editors.setupEditors({ cs, $, logJS, logJSX, logJSExec });
    } else {
      logJS('Editors module не найден — редакторы отключены.');
    }
    bootstrapJSX();
    pullStateFromJsx(); // подтянем текущее состояние в UI при старте
    logJS("Панель готова. Подписка echo: ВКЛ. ExtendScript редактор активен. JS редактор активен.");
  }

  // ============================================================================
  // 14) DOM Ready
  // ============================================================================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

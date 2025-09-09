//JSX (Extend script in Premiere Pro) based on ECMAscript 3! The code should be ES3 compatible.
(function () {
  try {
    if (!$.global.CepJsxBridge) $.global.CepJsxBridge = {};
    var BR = $.global.CepJsxBridge;

    // Подгружаем PlugPlug для событий
    if (!BR._plugOk) {
      try {
        BR._plug = new ExternalObject("lib:PlugPlugExternalObject");
        BR._plugOk = true;
      } catch (e) {
        try { $.writeln("PlugPlug load failed: " + e); } catch (_) {}
        return "PlugPlug load failed: " + e;
      }
    }

    // Типы событий
    BR.EVENT       = "app.bridge.echo";
    BR.LOG         = "app.bridge.log";
    BR.REQPROC     = "app.bridge.proc.run"; // НОВОЕ: универсальный запуск программы через CEP
      // === События для таймингов/SRT ===
    BR.PPRO_TIMINGS_START = "app.ppro.timings.start";
    BR.PPRO_TIMINGS_READY = "app.ppro.timings.ready";

    // --- Глобальное состояние ---
    BR.state = BR.state || {};

    // Общее хранилище настроек
    if (!BR.state.data || typeof BR.state.data !== "object") BR.state.data = {};
    if (typeof BR.state.data.projectPath  === "undefined") BR.state.data.projectPath  = "";
    if (typeof BR.state.data.languageCode === "undefined") BR.state.data.languageCode = "fr";
    if (typeof BR.state.data.csvPath === "undefined") BR.state.data.csvPath = "";
    if (typeof BR.state.data.audioPause === "undefined") BR.state.data.audioPause = 0.5;

    // Лог в панель
    BR._log = function (t) {
      try { var ev = new CSXSEvent(); ev.type = BR.LOG; ev.data = String(t); ev.dispatch(); } catch(_) {}
    };

    // === JSON.stringify для ES3 ===
    BR._esc = function (s) {
      s = String(s);
      s = s.replace(/\\/g, "\\\\");
      s = s.replace(/"/g, '\\"');
      s = s.replace(/\r/g, "\\r");
      s = s.replace(/\n/g, "\\n");
      return s;
    };
    BR._stringify = function (v) {
      if (v === null) return "null";
      var t = typeof v;
      if (t === "string") return '"' + BR._esc(v) + '"';
      if (t === "number" || t === "boolean") return String(v);
      if (t === "object") {
        // Array?
        if (v && v.splice && typeof v.length === "number") {
          var i, out = "[";
          for (i = 0; i < v.length; i++) { if (i) out += ","; out += BR._stringify(v[i]); }
          return out + "]";
        }
        var k, first = true, s = "{";
        for (k in v) if (v.hasOwnProperty(k)) {
          if (!first) s += ","; first = false;
          s += '"' + BR._esc(String(k)) + '":' + BR._stringify(v[k]);
        }
        return s + "}";
      }
      return "null"; // функции/undefined
    };

    // === Экспорт/импорт состояния ===
    BR.exportState = function () {
      try { return BR._stringify(BR.state || {}); }
      catch (e) { BR._log("exportState error: " + e); return "{}"; }
    };
    BR.importState = function (jsonStr) {
      try {
        var s = String(jsonStr || "{}");
        var obj = eval("(" + s + ")"); // ES3: нет JSON.parse
        if (obj && typeof obj === "object") { 
          BR.state = obj; 
          if (!BR.state.data || typeof BR.state.data !== "object") BR.state.data = {};
          if (typeof BR.state.data.projectPath  === "undefined") BR.state.data.projectPath  = "";
          if (typeof BR.state.data.languageCode === "undefined") BR.state.data.languageCode = "";
          if (typeof BR.state.data.audioPause === "undefined") BR.state.data.audioPause = 0.5;
          BR._log("importState OK"); return true; }
        BR._log("importState: not an object"); return false;
      } catch (e) { BR._log("importState error: " + e); return false; }
    };

    // === Сообщение в CEP ===
    BR.sendMessage = function (text) {
      try {
        var e = new CSXSEvent();
        e.type = BR.EVENT;
        e.data = String(text);
        e.dispatch();
        BR._log("JSX sent: " + text);
      } catch (ex) { BR._log("JSX send error: " + ex); }
    };

    // === НОВОЕ: Универсальный запуск программы через CEP ===
    // Варианты вызова (всё опционально, кроме program):
    //   runProgramFromJsx(program)
    //   runProgramFromJsx(program, filePath)
    //   runProgramFromJsx(program, filePath, argLine)
    //   runProgramFromJsx(program, /*argLine*/ "a b")   // если второй аргумент строка и 3-й не передан — трактуем как argLine
    //   runProgramFromJsx(program, /*args*/ ["--x", "y"]) // если второй аргумент массив — трактуем как args
    BR.runProgramFromJsx = function (program, opt2, opt3) {
      try {
        var payload = { program: String(program || "") };
        if (!payload.program) { BR._log("runProgramFromJsx: program is empty"); return false; }

        // Перегрузка параметров:
        // opt2 может быть: путь к файлу (string), строка аргументов (string), либо массив аргументов.
        if (typeof opt2 === "string" && typeof opt3 === "undefined") {
          // Трактуем opt2 как argLine (filePath опущен)
          if (opt2.length) payload.argLine = opt2;
        } else {
          if (typeof opt2 === "string" && opt2.length) payload.filePath = opt2;
          if (typeof opt3 === "string" && opt3.length) payload.argLine  = opt3;
        }
        if (opt2 && opt2.splice && typeof opt2.length === "number") {
          // opt2 — массив аргументов
          payload.args = opt2;
        }

        var ev = new CSXSEvent();
        ev.type = BR.REQPROC;
        ev.data = BR._stringify(payload);
        ev.dispatch();
        BR._log("PROC request sent from JSX");
        return true;
      } catch (ex) {
        BR._log("PROC request error: " + ex);
        return false;
      }
    };

        // Уведомить CEP: старт сбора таймингов
    BR.notifyTimingsStart = function () {
      try {
        var ev = new CSXSEvent();
        ev.type = BR.PPRO_TIMINGS_START;
        ev.data = "start";
        ev.dispatch();
        BR._log("PPRO timings: start");
        return true;
      } catch (ex) { BR._log("notifyTimingsStart error: " + ex); return false; }
    };

    // Уведомить CEP: готов JSON (data = путь к JSON)
    BR.notifyTimingsReady = function (jsonPath) {
      try {
        var ev = new CSXSEvent();
        ev.type = BR.PPRO_TIMINGS_READY;
        ev.data = String(jsonPath || "");
        ev.dispatch();
        BR._log("PPRO timings: ready → " + String(jsonPath || ""));
        return true;
      } catch (ex) { BR._log("notifyTimingsReady error: " + ex); return false; }
    };


BR._log("JSX ready");
"BOOTSTRAP_OK";
} catch (ex) {
  try { var e = new CSXSEvent(); e.type = "app.bridge.log"; e.data = "bootstrap error: " + ex; e.dispatch(); } catch(_) {}
  "BOOTSTRAP_FAIL";
}

})();

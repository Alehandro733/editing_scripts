// ECMAscript 3 only!

function __noop_bootstrap__(){ return "OK"; }
// Кол-во "тиков" в секунде у Premiere:
var TICKS_PER_SECOND = 254016000000;

/********************
 * ОБЩИЕ УТИЛИТЫ 
 ********************/
//Проверка что number есть float и выдаем его. Если нет, то выдаем defValue
function checkIfFloat(number, defValue) {
    var numberFloat = parseFloat(number);
    if (isNaN(numberFloat)) {
        // Если не число, подставляем дефолтное значение
        alert("введеное значение \"" + number + ("\" не является float. Использовано значение по умолчанию - \"" + defValue + "\""))
        return defValue;
    }
    else {
        // Иначе используем преобразованное значение
        return numberFloat;
    }
}

// Проверка активной секвенции
function getActiveSequence() {
    var seq = app.project.activeSequence;
    if (!seq) throw new Error("Нет активной секвенции!");
    return seq;
}

function getClipIds(track) {
    var ids = [];
    for (var i = 0; i < track.clips.numItems; i++)
        ids.push(track.clips[i].nodeId);
    return ids;
}

// Получить клипы по массиву ID из указанного трека
function getClipsByIds(track, clipIds) {
    var result = [];
    for (var i = 0; i < clipIds.length; i++) {
        for (var j = 0; j < track.clips.numItems; j++) {
            var clip = track.clips[j];
            if (clip.nodeId === clipIds[i]) {
                result.push(clip);
                break;
            }
        }
    }
    return result;
}

//Получить выделенные клипы из указанного объекта трека или массива (array) треков) TrackCollection не подходит, но подойдет так: app.project.sequences[index].audioTracks[index]
function getSelectedClipsFromTrack(tracks) {
    var trackArray = (tracks instanceof Array) ? tracks : [tracks];
    
    var selectedClips = [];
    for (var t = 0; t < trackArray.length; t++) {
        var track = trackArray[t];
        for (var c = 0; c < track.clips.length; c++) {
            var clip = track.clips[c];
            if (clip.isSelected()) {
                selectedClips.push(clip);
            }
        }
    }
    return selectedClips;
}

//Получить выделенные клипы из указанной коллекции TrackCollection (app.project.sequences[index].audioTracks или app.project.sequences[index].videoTracks)
function getSelectedClips(tracksCollection) {
    var selectedClips = [];
    for (var t = 0; t < tracksCollection.length; t++) {
        var track = tracksCollection[t];
        for (var c = 0; c < track.clips.length; c++) {
            var clip = track.clips[c];
            if (clip.isSelected()) selectedClips.push(clip);
        }
    }
    return selectedClips;
}

/*       получает объект Клипа clip, startSec - время в секундах куда переместится клип, endSec - концовка клип            */
function setClipStartEnd(clip, startSec, endSec) {
    // Вычисляем смещение относительно текущего времени начала клипа
    
    var shift = startSec - clip.start.seconds;
    clip.move(shift);
    // Устанавливаем время окончания клипа как новый объект Time
    var endTime = new Time();
    endTime.seconds = endSec;
    clip.end = endTime;
}

// Вспомогательные функции для выравнивания
function sortByStart(a, b) {
    return a.start.seconds - b.start.seconds;
}

function alignClips(movingClips, referenceClips) {
    for (var i = 0; i < movingClips.length; i++) {
        var movingClip = movingClips[i];
        var referenceClip = referenceClips[i];
        var endTime;
        
        if (i < movingClips.length - 1) {
            endTime = referenceClips[i + 1].start.seconds;
        }
        else {
            endTime = referenceClip.end.seconds;
        }
        setClipStartEnd(movingClip, referenceClip.start.seconds, endTime);
    }
}

/** 
 * Функции для кнопок 
 */

/********************
 * ФУНКЦИОНАЛ ZIGZAG 
 ********************/
// 1 аудио трек - на нем будет 1 клип, за ним 1 клип с 2 трека и тд.
function zigZagAudioClipsWithOffset(gapSec1, gapSec2, firstTrackNumber, secondTrackNumber) {
    
    function processZigZag(clipsA, tracksB, offsetA, offsetB) {
        //setClipStartEnd(clipsA[0], 0, clipsA[0].duration.seconds); (перестановка 1 клипа в самое начало. Сейчас убрал)
        var nextTime = clipsA[0].end.seconds + offsetA;
        
        for (var i = 0; i < Math.min(clipsA.length, tracksB.length); i++) {
            var clipB = tracksB[i];
            setClipStartEnd(clipB, nextTime, nextTime + clipB.duration.seconds);
            nextTime = clipB.end.seconds + offsetB;
            
            if (i + 1 >= clipsA.length) break;
            
            var nextClipA = clipsA[i + 1];
            setClipStartEnd(nextClipA, nextTime, nextTime + nextClipA.duration.seconds);
            nextTime = nextClipA.end.seconds + offsetA;
        }
    }
    
    ///////// на всякий случай проверка входных параметров временно
    gapSec1 = checkIfFloat(gapSec1, 0.5); // пауза после клипа с верхнего трека
    gapSec2 = checkIfFloat(gapSec2, 0.2); // пауза после клипа с нижнего трека
    
    
    firstTrackNumber = firstTrackNumber || 1; //номера треков по умолчанию, потом я вычту из них 1 единицу 
    secondTrackNumber = secondTrackNumber || 2;
    
    try {
        var seq = getActiveSequence();
        var audioTracks = seq.audioTracks;
        
        if (audioTracks.numTracks < 2)
            throw new Error('В секвенции "' + seq.name + '" нет 2 аудиодорожек');
        
        var trackA = audioTracks[firstTrackNumber - 1];
        var trackB = audioTracks[secondTrackNumber - 1];
        
        var trackAClips = getSelectedClipsFromTrack(trackA);
        var trackBClips = getSelectedClipsFromTrack(trackB);
        
        trackAClips.sort(sortByStart);
        trackBClips.sort(sortByStart);
        
        
        var lenA = trackAClips.length;
        var lenB = trackBClips.length;
        if (Math.abs(lenA - lenB) > 1) {
            throw new Error(
                "Разница между количеством выбарнных клипов на 1 и 2 треках не может быть больше 1 \n\n" +
                "На первом треке выбрано " + lenA + " клипов \n" +
                "На втором треке выбрано " + lenB + " клипов"
            );
        }
        
        processZigZag(trackAClips, trackBClips, gapSec1, gapSec2);
        alert("Зиг-заг выполнен в секвенции \"" + seq.name + "\"");
    }
    catch (e) {
        alert(e.message);
    }
}

/********************
 * ВЫРАВНИВАНИЕ ВИДЕО
 ********************/

function alignSelectedVideoToAudio() {
    try {
        var seq = getActiveSequence();
        var videoClips = getSelectedClips(seq.videoTracks);
        var audioClips = getSelectedClips(seq.audioTracks);
        
        if (!videoClips.length || !audioClips.length)
            throw new Error("Нет выделенных клипов");
        
        if (audioClips.length < videoClips.length)
            throw new Error("Аудио-клипов меньше чем видео");
        
        videoClips.sort(sortByStart);
        audioClips.sort(sortByStart);
        
        alignClips(videoClips, audioClips);
        alert("Видео клипы выровнены под аудио клипы");
    }
    catch (e) {
        alert(e.message);
    }
}

function glueSelectedAudioClipsAddGap(gap) {
    
    var seq = getActiveSequence();
    
    var GAP_DURATION = checkIfFloat(gap, 0);
    
    var selectedClips = getSelectedClips(seq.audioTracks);
    
    if (selectedClips.length < 2) {
        alert("Выделите минимум 2 клипа на аудиодорожках! Скрипт остановлен.");
        return;
    }
    
    // Сортируем по времени старта
    selectedClips.sort(sortByStart);
    
    // 5) Перемещаем подряд с заданным промежутком
    var currentTime = selectedClips[0].start.seconds + selectedClips[0].duration.seconds;
    for (var i = 1; i < selectedClips.length; i++) {
        var clip = selectedClips[i];
        var dur = clip.duration.seconds;
        var newStart = currentTime + GAP_DURATION;
        var newEnd = newStart + dur;
        setClipStartEnd(clip, newStart, newEnd);
        currentTime = newEnd;
    }
    
    alert("Клипы перемещены, промежуток между ними: " + GAP_DURATION + " сек");
}

/** 
 * Вспомогательные функции для работы с CSV
 */

/**
 * функция-помошник для передачи пути или выбора файла
 * Возвращает открытый для чтения File с CSV:
 * — если передали File или строку, пытаемся использовать их;
 * — иначе показываем диалог.
 *
 * @param {File|string=} path_or_File
 * @returns {File|null} — либо готовый File, либо null
 */
function getCsvFile(path_or_File) {
    // Если передали строку — оборачиваем
    if (typeof path_or_File === "string") {
        path_or_File = new File(path_or_File);
    }
    // Если ничего не передали — диалог
    else if (path_or_File == null) {
        path_or_File = File.openDialog("Выберите CSV файл", "*.csv");
    }
    // Если файл не выбран или не открывается — отменяем
    if (!path_or_File || !path_or_File.open("r")) {
        alert(path_or_File ?
            "Ошибка открытия файла: " + path_or_File.fsName :
            "CSV не выбран.");
        return null;
    }
    return path_or_File;
}

function parseCSVLine(line) {
    var result = [];
    var curVal = "";
    var inQuotes = false;
    var c;
    for (var i = 0; i < line.length; i++) {
        c = line.charAt(i);
        if (c === '"') {
            // Если уже в кавычках и следующая тоже кавычка -> экранирование
            if (inQuotes && i < line.length - 1 && line.charAt(i + 1) === '"') {
                curVal += '"';
                i++;
            }
            else {
                inQuotes = !inQuotes; // переключаем флаг
            }
        }
        else if (c === ',' && !inQuotes) {
            // Запятая вне кавычек -> завершение колонки
            result.push(curVal);
            curVal = "";
        }
        else {
            // Все остальные символы или запятые внутри кавычек
            curVal += c;
        }
    }
    // Добавляем последний накопленный столбец
    result.push(curVal);
    return result;
}

/**
 * Извлекает из CSV индексы строк-маркеров и сами значения меток в заданной колонке.
 * @param {string} csvText    — содержимое CSV (любой перевод строк).
 * @param {string} columnName — имя колонки для поиска меток.
 * @returns {{
 *   rows: string[],
 *   markers: number[],
 *   markerValues: number[],
 *   totalDataRows: number
 * }}
 * @throws {Error} если нет данных или колонки.
 */
function extractCsvMarkers(csvText, columnName) {
    // 1) Нормализуем переводы строк и разбиваем на строки
    var text = csvText.replace(/\r\n/g, "\n")
        .replace(/\r/g, "\n");
    var rows = text.split("\n");
    if (rows.length < 2) {
        throw new Error("CSV содержит только заголовок или пуст.");
    }
    
    // 2) Ищем индекс колонки columnName в заголовке
    var headerCols = parseCSVLine(rows[0]);
    var colIdx = -1;
    for (var i = 0; i < headerCols.length; i++) {
        if (headerCols[i].replace(/^\s+|\s+$/g, "") === columnName) {
            colIdx = i;
            break;
        }
    }
    if (colIdx < 0) {
        throw new Error('Колонка "' + columnName + '" не найдена в заголовке.');
    }
    
    // 3) Собираем номера строк-маркеров и их числовые значения
    var markers = [];
    var markerValues = [];
    for (var r = 1; r < rows.length; r++) {
        var line = rows[r];
        if (!line || /^\s*$/.test(line)) {
            continue; // пропускаем пустые строки
        }
        var cols = parseCSVLine(line);
        if (cols.length <= colIdx) {
            continue; // нет нужной колонки
        }
        var val = cols[colIdx].replace(/^\s+|\s+$/g, "");
        if (/^\d+$/.test(val)) {
            markers.push(r);
            markerValues.push(parseInt(val, 10));
        }
    }
    
    // 4) Считаем общее число строк-данных (без заголовка и с пропуском последней строки, если она пустая)
    var totalDataRows = rows.length - 1;
    if (/^\s*$/.test(rows[rows.length - 1])) {
        totalDataRows--;
    }
    return {
        rows: rows,
        markers: markers,
        markerValues: markerValues,
        totalDataRows: totalDataRows
    };
}

/* Align selected audio clips to markers from a CSV file 
 * targetTrackNumber — 1‑based номер трека, где выделены клипы, которые НУЖНО переместить.
 * На остальных выделенных аудиотреках должны быть «маячные» клипы.
 */
function AlignAudioClipsToCsvMarks(targetTrackNumber, csvFile) {
    
    // Premiere Pro использует 0‑based индексы треков
    targetTrackNumber = targetTrackNumber - 1;
    
    var seq = app.project.activeSequence;
    if (!seq) {
        alert("Нет активной секвенции!");
        return;
    }
    
    // ===== 1. Получаем CSV-файл =====
    csvFile = getCsvFile(csvFile);
    if (!csvFile) return;
    var csvContent = csvFile.read();
    csvFile.close();
    
    /* ===== 2. Извлекаем метки из колонки \"audio\" ===== */
    var data;
    try {
        data = extractCsvMarkers(csvContent, "audio");
    }
    catch (e) {
        alert(e.message);
        return;
    }
    var markers = data.markers; // массив номеров строк‑меток (1‑based)
    
    /* ===== 3. Собираем все выбранные аудио‑клипы ===== */
    var audioTracks = seq.audioTracks;
    var selectedAllClips = getSelectedClips(audioTracks);
    
    /* Проверяем корректность номера трека‑приёмника */
    if (targetTrackNumber < 0 || targetTrackNumber >= audioTracks.length) {
        alert("Неверный номер трека: " + (targetTrackNumber + 1));
        return;
    }
    
    /* ===== 4. Делим на moveClips и targetClips ===== */
    
    // 4.1  moveClips — выделенные клипы НА указанном треке (их будем двигать)
    var moveClips = getSelectedClips([audioTracks[targetTrackNumber]]);
    
    // 4.2  targetClips — все остальные выделенные клипы (по ним выравниваем)
    function arrayContains(arr, value) {
        for (var i = 0; i < arr.length; i++) {
            if (arr[i] === value) return true;
        }
        return false;
    }
    
    // nodeId‑ы moveClips, чтобы быстро фильтровать
    var moveIds = [];
    for (var i = 0; i < moveClips.length; i++) {
        moveIds.push(moveClips[i].nodeId);
    }
    
    var targetClips = [];
    for (var j = 0; j < selectedAllClips.length; j++) {
        var clip = selectedAllClips[j];
        if (!arrayContains(moveIds, clip.nodeId)) {
            targetClips.push(clip);
        }
    }
    
    /* ===== 5. Сортировка по времени старта ===== */
    targetClips.sort(sortByStart);
    moveClips.sort(sortByStart);
    
    /* ===== 6. Проверяем соответствие количеств ===== */
    if (moveClips.length !== markers.length) {
        alert("Количество меток (" + markers.length + ") не совпадает с клипами к перемещению (" + moveClips.length + ")");
        return;
    }
    
    /* ===== 6.1 Проверяем, хватает ли target‑клипов ===== */
    var maxRowIdx = 0;
    for (var m = 0; m < markers.length; m++) {
        if (markers[m] > maxRowIdx) maxRowIdx = markers[m];
    }
    if (targetClips.length < maxRowIdx) {
        alert("Выделено целевых клипов: " + targetClips.length + "\nПоследняя метка ссылается на клип № " + maxRowIdx + "\nВыберите как минимум " + maxRowIdx + " целевых клипов.");
        return;
    }
    
    /* ===== 7. Перемещаем каждый клип ===== */
    for (var k = 0; k < markers.length; k++) {
        var rowIdx = markers[k]; // номер строки CSV (1‑based)
        var target = targetClips[rowIdx - 1];
        var mover = moveClips[k];
        
        if (!target) continue; // защита от выхода за пределы
        
        var offset = target.start.seconds - mover.start.seconds;
        var tOff = new Time();
        tOff.seconds = offset;
        mover.move(tOff);
    }
    
    alert("Успешно перемещено " + markers.length + " клипов!");
}

function AlignImagesToCsvMarks(csvFile) {
    // ===== 1. Активная секвенция =====
    var seq = app.project.activeSequence;
    if (!seq) {
        alert("Нет активной секвенции!");
        return;
    }
    
    csvFile = getCsvFile(csvFile);
    if (!csvFile) return;
    var csvContent = csvFile.read();
    csvFile.close();
    
    /* ===== 2. Извлекаем markers из колонки "images" ===== */
    var data;
    try {
        data = extractCsvMarkers(csvContent, "images");
    }
    catch (e) {
        alert(e.message);
        return;
    }
    var markers = data.markers; // массив номеров строк‑маркеров
    var totalDataRows = data.totalDataRows; // всего строк‑данных
    
    if (markers.length < 2) {
        alert("Недостаточно цифровых меток (найдено: " + markers.length + ")");
        return;
    }
    
    /* ===== 3. Собираем выделенные клипы ===== */
    var selectedAudioClips = getSelectedClips(seq.audioTracks);
    var selectedVideoClips = getSelectedClips(seq.videoTracks);
    
    selectedAudioClips.sort(sortByStart);
    selectedVideoClips.sort(sortByStart);
    
    /* ===== 4. Проверяем количества ===== */
    if (selectedAudioClips.length !== totalDataRows) {
        alert(
            "Неверное число аудио‑клипов.\n" +
            "Строк CSV (без заголовка): " + totalDataRows + "\n" +
            "Выделено аудио‑клипов: " + selectedAudioClips.length
        );
        return;
    }
    if (selectedVideoClips.length !== (markers.length - 1)) {
        alert(
            "Неверное число видео‑клипов.\n" +
            "Маркеров: " + markers.length + " ⇒ видео‑клипов нужно: " + (markers.length - 1) + "\n" +
            "Выделено: " + selectedVideoClips.length
        );
        return;
    }
    
    /* ===== 5. Выравнивание видео под аудио ===== */
    for (var v = 0; v < selectedVideoClips.length; v++) {
        var videoClip = selectedVideoClips[v],
            startSec = selectedAudioClips[markers[v] - 1].start.seconds,
            endSec,
            nextMarker = markers[v + 1];
        
        if (v < selectedVideoClips.length - 1) {
            // не последний клип — конец = старт следующего маркера
            endSec = selectedAudioClips[nextMarker - 1].start.seconds;
        }
        else if (nextMarker && nextMarker - 1 < selectedAudioClips.length) {
            // последний клип и есть аудиоклип для маркера v+1 — конец = его конец
            endSec = selectedAudioClips[nextMarker - 1].end.seconds;
        }
        else {
            // Нет – берём конец самого последнего аудио
            endSec = selectedAudioClips[selectedAudioClips.length - 1].end.seconds;
        }
        
        setClipStartEnd(videoClip, startSec, endSec);
    }
    
    alert("Видео‑клипы успешно выровнены по меткам из CSV!");
}

/** 
 * Новые функции
 */


// ===== mini‑лог‑хелпер =====
function myLog(msg) { alert(msg); }


/**
 * Импортирует папку или файл в корень активного проекта Premiere Pro.
 *
 * @param {string} absFilePath — абсолютный путь к файлу в файловой системе Windows.
 */
function importSingleFile(absFilePath) {
    
    var project = app.project,
        rootBin = project.rootItem,
        fileObj = new File(absFilePath);
    
    if (!fileObj.exists) {
        myLog("Файл не найден:\n" + absFilePath);
        return;
    }
    
    // импортируем массивом из одного пути
    var suppressWarnings = true,
        importAsStills = false; // по умолчанию
    project.importFiles(
        [fileObj.fsName],
        suppressWarnings,
        rootBin,
        importAsStills
    );
    
    //    myLog("Файл «" + fileObj.name + "» успешно импортирован.");
}

//////////////////////////////////////

// ===== 1. Поиск bin по «пути» вида "data/images" =====
function findBinByPath(binPath) {
    var parts = binPath.split("/"),
        current = app.project.rootItem;
    
    for (var i = 0; i < parts.length; i++) {
        var found = false;
        for (var j = 0; j < current.children.numItems; j++) {
            var child = current.children[j];
            if (child.type === ProjectItemType.BIN && child.name === parts[i]) {
                current = child;
                found = true;
                break;
            }
        }
        if (!found) { return null; }
    }
    return current;
}

// ===== 2. Поиск одиночного файла в корне =====
function findFileInRoot(name) {
    var root = app.project.rootItem;
    for (var i = 0; i < root.children.numItems; i++) {
        var ch = root.children[i];
        if (ch.type !== ProjectItemType.BIN && ch.name === name) {
            return ch;
        }
    }
    return null;
}

// ===== 3. Сбор медиа из bin (рекурсивно), отбирая только нужные расширения =====
function collectMediaFromBin(binItem, regex) {
    var out = [];
    for (var i = 0; i < binItem.children.numItems; i++) {
        var ch = binItem.children[i];
        if (ch.type === ProjectItemType.BIN) {
            out = out.concat(collectMediaFromBin(ch, regex));
        }
        else if (regex.test(ch.name)) {
            out.push(ch);
        }
    }
    return out;
}

/**
 * ищет ProjectItem’ы по путям и выводит alert’ы.
 *
 * @param {string[]} paths   — массив путей (имена файлов или bin-пути через "/")
 * @param {string[]=} filter — массив из {"video","audio","images"} и/или своих 
 *                             расширений (".png","mp3", "svg") либо raw‑regex строк "/.../i".
 *                             Если не задан или пустой — без фильтра (все items).
 * @returns {ProjectItem[]}
 */
function resolveItemsByPaths(paths, filter) {
    // 1) Определяем, нужен ли вообще фильтр
    var noFilter = (filter == null) || !(filter instanceof Array) || (filter.length === 0);
    
    // 2) Базовые регулярки
    var vr = /\.(mp4|mov|avi|mkv)$/i;
    var ar = /\.(wav|mp3|aac|flac)$/i;
    var ir = /\.(jpg|jpeg|png|gif|bmp|webp)$/i;
    
    // 3) Собираем общий RegExp
    var combinedRe;
    if (noFilter) {
        combinedRe = /.*/i; // всё пропускаем
    }
    else {
        var parts = [];
        for (var i = 0; i < filter.length; i++) {
            var f = filter[i];
            if (typeof f !== "string") { continue; }
            var key = f.toLowerCase();
            
            // 3.1) Алиасы
            if (key === "video") {
                parts.push(vr.source);
                continue;
            }
            if (key === "audio") {
                parts.push(ar.source);
                continue;
            }
            if (key === "images" || key === "image") {
                parts.push(ir.source);
                continue;
            }
            
            // 3.2) Raw‑регулярка: строка вида "/pattern/flags"
            if (f.charAt(0) === "/" && f.lastIndexOf("/") > 0) {
                var last = f.lastIndexOf("/");
                var patt = f.substring(1, last);
                var flags = f.substring(last + 1);
                try {
                    // Проверим, что это валидный RegExp
                    var tmp = new RegExp(patt, flags);
                    parts.push(tmp.source);
                }
                catch (e) {
                    // Игнорируем некорректное
                }
                continue;
            }
            
            // 3.3) Рассматриваем как расширение
            //      убираем ведущую точку, экранируем точку в начале и ставим $ на конец
            var ext = (f.charAt(0) === ".") ? f.slice(1) : f;
            // экранируем возможные спецсимволы
            ext = ext.replace(/[-\\^$*+?.()|[\]{}]/g, "\\$&");
            parts.push("\\." + ext + "$");
        }
        
        // 3.4) Если после всего нет частей — тоже без фильтра
        if (parts.length === 0) {
            combinedRe = /.*/i;
        }
        else {
            combinedRe = new RegExp(parts.join("|"), "i");
        }
    }
    
    // 4) Основной обход путей (как раньше)
    var result = [];
    for (var idx = 0; idx < paths.length; idx++) {
        var p = paths[idx];
        //    alert("Обрабатываем путь [" + idx + "]: " + p);
        
        if (p.indexOf("/") >= 0) {
            var bin = findBinByPath(p);
            if (!bin) { alert("Bin не найден: " + p); continue; }
            //        alert("Bin найден: " + p + " (items: " + bin.children.numItems + ")");
            var media = collectMediaFromBin(bin, combinedRe);
            //        alert("Найдено в bin: " + media.length);
            for (var m = 0; m < media.length; m++) result.push(media[m]);
        }
        else {
            var fileItem = findFileInRoot(p);
            if (fileItem) {
                //            alert("Файл в корне: " + p);
                result.push(fileItem);
            }
            else {
                var b = findBinByPath(p);
                if (b) {
                    //                alert("Bin по имени: " + p + " (items: " + b.children.numItems + ")");
                    var media2 = collectMediaFromBin(b, combinedRe);
                    //                alert("Найдено в bin: " + media2.length);
                    for (var m2 = 0; m2 < media2.length; m2++) result.push(media2[m2]);
                }
                else {
                    alert("Не найден: " + p);
                }
            }
        }
    }
    
    // 5) Отчёт
    // if (result.length) {
    //     var names = [];
    //     for (var i = 0; i < result.length; i++) names.push(result[i].name);
    //     alert("Итог: " + result.length + " -> " + names.join(", "));
    // } else {
    //     alert("Итог: ничего не найдено.");
    // }
    
    return result;
}

/**
 * Ищет ProjectItem по точному пути внутри проекта.
 * Путь — строка вида "Bin1/Bin2/.../ItemName.ext" или просто "ItemName.ext" (в корне).
 *
 * @param {string} path  — путь через "/", например "data/subtitles.srt"
 * @returns {ProjectItem|null} — найденный элемент или null, если не найден
 */
function getProjectItemByPath(path) {
    // Стартуем с корневого бина проекта
    var currentBin = app.project.rootItem;
    if (!currentBin || !currentBin.children) {
        return null;
    }
    
    // Разбиваем путь на сегменты
    var parts = path.split("/");
    
    // Проходим по всем сегментам
    for (var i = 0; i < parts.length; i++) {
        var nameToFind = parts[i];
        var found = null;
        
        // Ищем в текущем бине ребёнка с нужным именем
        for (var j = 0; j < currentBin.children.numItems; j++) {
            var child = currentBin.children[j];
            if (child && child.name === nameToFind) {
                found = child;
                break;
            }
        }
        
        // Если не нашли — возвращаем null
        if (!found) {
            return null;
        }
        
        // Если это не последний сегмент, убеждаемся, что нашли бин, и спускаемся в него
        if (i < parts.length - 1) {
            if (found.type === ProjectItemType.BIN) {
                currentBin = found;
            }
            else {
                // Нашли файл там, где ожидали бин
                return null;
            }
        }
        else {
            // Последний сегмент — это искомый ProjectItem
            return found;
        }
    }
    
    return null; // теоретически сюда не дойдём
}

/**
 * Укладывает массив ProjectItem‑ов на таймлайн, вставляя их
 * в **обратном порядке** в одну и ту же точку (`startSec`)
 * с помощью insertClip(). Каждый новый клип сдвигает предыдущие вправо,
 * поэтому итоговый порядок на дорожке будет прямой (1‑2‑3…).
 *
 * @param {ProjectItem[]} items      — список из resolveItemsByPaths()
 * @param {'audio'|'video'} trackType — тип трека
 * @param {number}        trackIndex  — индекс трека (0‑based)
 * @param {number}        startSec    — время начала в секундах
 */
function placeItemsOnTimeline(items, trackType, trackIndex, startSec) {
    
    function log(m) { 
        //alert(m); 
    }
    
    var seq = app.project.activeSequence;
    if (!seq) { log("Нет активной секвенции."); return; }
    
    // выбираем аудио‑ или видео‑трек
    var track = (trackType === "audio") ? seq.audioTracks[trackIndex] :
        seq.videoTracks[trackIndex];
    if (!track) { log("Трек " + trackType + "[" + trackIndex + "] не найден."); return; }
    
    log("Начинаем вставку " + items.length + " элементов в " + trackType +
        "[" + trackIndex + "] c позиции " + startSec + " сек.");
    
    // === вставляем с КОНЦА массива, чтобы первый клип оказался самым левым ===
    for (var i = items.length - 1; i >= 0; i--) {
        var itm = items[i];
        if (!itm) continue;
        
        track.insertClip(itm, startSec); // каждую вставку — в точку startSec
        //log("Вставлен: "+itm.name);
    }
    
    log("Готово: уложено " + items.length + " клипов.");
}

/**
 * Размещает переданный .srt ProjectItem на новом caption-треке активной секвенции.
 *
 * @param {ProjectItem} srtItem  — ProjectItem с .srt-файлом, который уже импортирован в проект
 * @param {number=}     startSec — время начала в секундах (по умолчанию 0)
 * @returns {boolean}            — true, если трек создан и субтитры добавлены, иначе false
 */
function placeSrtProjectItemOnNewCaptionTrack(srtItem, startSec) {
    function log(msg) { alert(msg); }
    
    // Проверяем активную секвенцию
    var seq = app.project.activeSequence;
    if (!seq) {
        log("Нет активной секвенции.");
        return false;
    }
    
    // Проверяем переданный ProjectItem
    if (!srtItem || srtItem.type !== ProjectItemType.CLIP) {
        log("Неверный ProjectItem: ожидается импортированный .srt-клип.");
        return false;
    }
    
    // Время старта
    var time = (typeof startSec === "number") ? startSec : 0;
    
    log("Создаём новый caption-трек и добавляем субтитры с " + time + " сек.");
    
    // Создаём новый caption-трек с .srt внутри
    // (captionFormat можно передать третьим аргументом, по умолчанию Subtitle)
    var result = seq.createCaptionTrack(srtItem, time);
    
    if (!result) {
        log("Не удалось создать caption-трек.");
        return false;
    }
    
    log("Caption-трек успешно создан.");
    return true;
}

/**
 *  Возвращает массив всех клипов на указанном треке (audio или video).
 *
 * @param {string} trackType    — "audio" или "video"
 * @param {number} trackIndex   — индекс трека (0‑based)
 * @returns {TrackItem[]}       — массив клипов (может быть пустым)
 */
function getClipsOnTrack(trackType, trackIndex) {
    var seq = app.project.activeSequence;
    if (!seq) {
        alert("Нет активной секвенции.");
        return [];
    }
    
    var tracks;
    if (trackType === "audio") {
        tracks = seq.audioTracks;
    }
    else if (trackType === "video") {
        tracks = seq.videoTracks;
    }
    else {
        alert("Неверный тип трека: " + trackType);
        return [];
    }
    
    // Premiere Pro Scripting: audioTracks.numTracks, videoTracks.numTracks
    if (trackIndex == null || isNaN(trackIndex) ||
        trackIndex < 0 || trackIndex >= tracks.numTracks) {
        alert("Трек " + trackType + "[" + trackIndex + "] не найден.");
        return [];
    }
    
    var track = tracks[trackIndex];
    var clips = [];
    // Каждый трек имеет коллекцию clips с .numItems
    for (var i = 0; i < track.clips.numItems; i++) {
        var clip = track.clips[i];
        if (clip) {
            clips.push(clip);
        }
    }
    return clips;
}

/**
 *  Выбирает (select) все переданные клипы.
 *
 * @param {TrackItem[]} clipsArray — массив TrackItem’ов
 */
function selectClips(clipsArray) {
    if (!clipsArray || !(clipsArray instanceof Array)) {
        return;
    }
    for (var i = 0; i < clipsArray.length; i++) {
        var clip = clipsArray[i];
        if (clip && typeof clip.setSelected === "function") {
            // state = 1 (selected), updateUI = 1
            clip.setSelected(1, 1);
        }
    }
}


/**
 * 3 Снимает выделение (deselect) со всех клипов во всех audio и video треках.
 */
function deselectAllClips() {
    var seq = app.project.activeSequence;
    if (!seq) {
        return;
    }
    
    // вспомогательная функция для одного набора треков
    function deselectInTracks(tracks) {
        for (var t = 0; t < tracks.numTracks; t++) {
            var track = tracks[t];
            for (var i = 0; i < track.clips.numItems; i++) {
                var clip = track.clips[i];
                if (clip && typeof clip.setSelected === "function") {
                    // state = 0 (deselected), updateUI = 1
                    clip.setSelected(0, 1);
                }
            }
        }
    }
    
    deselectInTracks(seq.audioTracks);
    deselectInTracks(seq.videoTracks);
}


/********************
 * СОХРАНЕНИЕ ВСЕХ КЛИПОВ В CSV С СОРТИРОВКОЙ ES3
 * Собирает данные со всех клипов всех аудио- и видео-треков,
 * сортирует по start_time (insertion sort) и создаёт CSV-файл на рабочем столе: clips_timing.csv
 ********************/
function collectAllClipsTimingToCsv() {
    try {
        var seq = getActiveSequence();
        var header = "track,clip_number,start_time,end_time";
        var dataLines = [];
        
        // Обработка видео-треков
        var videoTracks = seq.videoTracks;
        for (var t = 0; t < videoTracks.numTracks; t++) {
            var track = videoTracks[t];
            for (var c = 0; c < track.clips.numItems; c++) {
                var clip = track.clips[c];
                var startVal = parseFloat(clip.start.seconds.toFixed(3));
                var endVal = parseFloat(clip.end.seconds.toFixed(3));
                dataLines.push(
                    "video" + (t + 1) + "," + (c + 1) + "," + startVal.toFixed(3) + "," + endVal.toFixed(3)
                );
            }
        }
        
        // Обработка аудио-треков
        var audioTracks = seq.audioTracks;
        for (var t = 0; t < audioTracks.numTracks; t++) {
            var track = audioTracks[t];
            for (var c = 0; c < track.clips.numItems; c++) {
                var clip = track.clips[c];
                var startVal = parseFloat(clip.start.seconds.toFixed(3));
                var endVal = parseFloat(clip.end.seconds.toFixed(3));
                dataLines.push(
                    "audio" + (t + 1) + "," + (c + 1) + "," + startVal.toFixed(3) + "," + endVal.toFixed(3)
                );
            }
        }
        
        // Сортировка insertion sort по start_time (поле index 2)
        for (var i = 1; i < dataLines.length; i++) {
            var keyLine = dataLines[i];
            var keyParts = keyLine.split(",");
            var keyStart = parseFloat(keyParts[2]);
            var j = i - 1;
            while (j >= 0) {
                var currParts = dataLines[j].split(",");
                var currStart = parseFloat(currParts[2]);
                if (currStart > keyStart) {
                    dataLines[j + 1] = dataLines[j];
                    j--;
                }
                else {
                    break;
                }
            }
            dataLines[j + 1] = keyLine;
        }
        
        // Собираем финальные строки
        var outputLines = [header];
        for (var k = 0; k < dataLines.length; k++) {
            outputLines.push(dataLines[k]);
        }
        
        // Создание файла на рабочем столе
        var filePath = "C:/Users/Michail/Desktop/clips_timing.csv";
        var file = new File(filePath);
        file.encoding = "UTF-8";
        if (file.open("w")) {
            file.write(outputLines.join("\r\n"));
            file.close();
        }
        else {
            alert("Не удалось создать файл: " + filePath);
        }
    }
    catch (e) {
        alert("Ошибка: " + e.message);
    }
}


/** ES3-compatible ExtendScript for Premiere Pro (CEP) **/
/**
 * collectAudio1TimingsToJson()
 *  - Собирает start/end (в секундах, с округлением до 3 знаков) со 1-го аудиотрека (индекс 0)
 *  - Пишет JSON { start:[...], end:[...] } в <корень_расширения>/temp/ppro_timings.json
 *  - Шлёт события:
 *      app.ppro.timings.start  — перед началом
 *      app.ppro.timings.ready  — по завершении (payload = путь к JSON)
 */
function collectAudio1TimingsToJson() {
    try {
        var BR = ($.global && $.global.CepJsxBridge) ? $.global.CepJsxBridge : null;
        if (BR && BR.notifyTimingsStart) { try { BR.notifyTimingsStart(); } catch (_s) {} }

        if (!app || !app.project || !app.project.activeSequence) {
            return "ERR: Нет активной секвенции";
        }
        var seq = app.project.activeSequence;

        // --- берём аудиотрек №1 (0-based)
        var aTracks = seq.audioTracks;
        if (!aTracks || (aTracks.numTracks !== undefined && aTracks.numTracks < 1)) {
            return "ERR: В секвенции нет аудиотрека 1";
        }
        var track = aTracks[0];

        // --- обходим клипы
        var starts = [], ends = [];
        var n = track && track.clips ? (track.clips.numItems !== undefined ? track.clips.numItems :
                                         track.clips.length !== undefined ? track.clips.length : 0) : 0;

        for (var i = 0; i < n; i++) {
            var clip = track.clips[i];
            if (!clip || !clip.start || !clip.end) { continue; }
            var s = clip.start.seconds;
            var e = clip.end.seconds;
            // округление до миллисекунд
            s = parseFloat(s.toFixed(3));
            e = parseFloat(e.toFixed(3));
            starts.push(s);
            ends.push(e);
        }

        // --- JSON: { start:[...], end:[...] }
        var data = { start: starts, end: ends };

        // --- путь к корню расширения = родитель папки /jsx/ текущего файла
        var jsxFile = new File($.fileName);
        var extRoot = jsxFile.parent && jsxFile.parent.parent ? jsxFile.parent.parent.fsName : Folder.current.fsName;
        var outFile = new File(extRoot + "/temp/ppro_timings.json");
        outFile.parent.create();
        outFile.encoding = "UTF-8";

        // stringify (используем BR._stringify если есть, иначе fallback)
        var jsonStr = (BR && BR._stringify) ? BR._stringify(data) : (function toJSON(obj) {
            // минимальный ES3 stringifier для нашего простого объекта
            var i, s = '{"start":[';
            for (i = 0; i < obj.start.length; i++) { if (i) s += ','; s += String(obj.start[i]); }
            s += '],"end":[';
            for (i = 0; i < obj.end.length; i++)   { if (i) s += ','; s += String(obj.end[i]); }
            s += ']}';
            return s;
        })(data);

        if (!outFile.open("w")) {
            return "ERR: Не удалось открыть файл для записи: " + outFile.fsName;
        }
        outFile.write(jsonStr);
        outFile.close();

        // --- уведомим CEP
        var payloadPath = outFile.fsName; // платформенный путь
        if (BR && BR.notifyTimingsReady) {
            try { BR.notifyTimingsReady(payloadPath); } catch (_r) {}
        } else {
            // фоллбек на прямой CSXSEvent
            try { var ev = new CSXSEvent(); ev.type = "app.ppro.timings.ready"; ev.data = String(payloadPath); ev.dispatch(); } catch (_) {}
        }

        return "OK: " + payloadPath;
    } catch (e) {
        return "ERR: " + (e && e.message ? e.message : e);
    }
}

// Нормализует путь: любые /, \, \\ → Windows backslash (\)
function pathHandler(p) {
    if (p == null) return "";
    var s = String(p).replace(/^\s+|\s+$/g, ""); // trim для ES3
    s = s.replace(/\//g, "\\");                  // заменяем / на \
    s = s.replace(/\\{2,}/g, "\\");              // схлопываем повторы \
    return s;
}

// Экспорт по умолчанию: ...\presets\MFA_wav.epr → ...\temp\voice.wav
// Можно передать свои пути: exportVoiceWav(customPresetPath, customOutputPath)
function exportVoiceWav(presetPathOpt, outputPathOpt) {
    var seq = app.project.activeSequence;
    if (!seq) return false;

    var root = (new File($.fileName)).parent.parent.fsName; // ...\cep

    // Пути по умолчанию
    var defPresetPath = root + "\\presets\\MFA_wav.epr";
    var defOutputPath = root + "\\temp\\voice.wav";

    // Применяем кастомные пути (если переданы), с нормализацией
    var presetPath = presetPathOpt ? pathHandler(presetPathOpt) : defPresetPath;
    var outputPath = outputPathOpt ? pathHandler(outputPathOpt) : defOutputPath;

    // Логика автоподмены расширения — только когда используем дефолтный outputPath
    if (!outputPathOpt) {
        try {
            var ext = seq.getExportFileExtension(presetPath);
            if (ext) {
                ext = ("" + ext).replace(/^\./, "").toLowerCase();
                if (ext !== "wav") {
                    // меняем только .wav в конце дефолтного имени
                    outputPath = outputPath.replace(/\.wav$/i, "." + ext);
                }
            }
        } catch (e) { /* игнорируем: оставим .wav */ }
    }

    /*return*/ seq.exportAsMediaDirect(
        outputPath,
        presetPath,
        app.encoder.ENCODE_IN_TO_OUT
    );

        // эксперимент, копируем аудио в папку проекта
    try {
        var src = new File(outputPath);
        if (src.exists && typeof projectPath === "string" && projectPath) {
            var dstFolder = new Folder(projectPath);
            var dst = new File(dstFolder.fsName + "\\" + src.name); // сохраняем имя (voice.wav)
            src.copy(dst.fsName);
        }
    } catch (e) { /* тихо игнорируем сбои копирования */ }

}


// Если хочешь, можешь использовать свою getSelectedClips(tracksCollection).
// Здесь — самодостаточная версия под аудиодорожки активной секвенции.
function getSelectedAudioClips(seq) {
    var result = [];
    if (!seq || !seq.audioTracks) return result;

    var tracks = seq.audioTracks;
    var tracksLen = (typeof tracks.length === 'number') ? tracks.length : tracks.numTracks;

    for (var t = 0; t < tracksLen; t++) {
        var track = tracks[t];
        if (!track || !track.clips) continue;

        var clips = track.clips;
        var clipsLen = (typeof clips.length === 'number') ? clips.length : clips.numItems;

        for (var c = 0; c < clipsLen; c++) {
            var clip = clips[c];
            try {
                if (clip && clip.isSelected && clip.isSelected()) {
                    result.push(clip);
                }
            } catch (e) { /* пропускаем, если трек/клип экзотический */ }
        }
    }
    return result;
}

function secondsToTicksString(seconds) {
    // setInPoint / setOutPoint ждут СТРОКУ с количеством тиков
    return String(Math.round(seconds * TICKS_PER_SECOND));
}

function setInOutFromSelectedAudioClips() {
    var seq = app.project.activeSequence;
    if (!seq) {
        alert('Нет активной секвенции.');
        return;
    }

    // Если хочешь использовать свою функцию — просто раскомментируй строку ниже
    // var selectedClips = getSelectedClips(seq.audioTracks);
    var selectedClips = getSelectedAudioClips(seq);

    if (!selectedClips || !selectedClips.length) {
        alert('Нет выделенных аудиоклипов на таймлайне.');
        return;
    }

    var minStart = Number.POSITIVE_INFINITY;
    var maxEnd = -Number.MAX_VALUE;

    for (var i = 0; i < selectedClips.length; i++) {
        var clip = selectedClips[i];
        if (!clip.start || !clip.end) continue;

        var s = clip.start.seconds;
        var e = clip.end.seconds;

        if (typeof s === 'number' && typeof e === 'number') {
            if (s < minStart) minStart = s;
            if (e > maxEnd) maxEnd = e;
        }
    }

    if (!isFinite(minStart) || !isFinite(maxEnd)) {
        alert('Не удалось вычислить границы по выделенным клипам.');
        return;
    }

    // Ставим In/Out секвенции в тиках
    seq.setInPoint(secondsToTicksString(minStart));
    seq.setOutPoint(secondsToTicksString(maxEnd));
}

/**
 * Мьютит все аудиодорожки активной секвенции,
 * КРОМЕ тех, чьи индексы указаны в параметре `excluded`.
 *
 * @param {number[]} excluded - Массив индексов аудиодорожек,
 * которые должны остаться размьюченными.  
 * Индексация начинается с 0 (левая дорожка = 0, следующая = 1 и т.д.).  
 * Если массив пустой или не передан, будут замьючены все дорожки.
 */
function muteAllAudioExcept(excluded) {
    var seq = app.project.activeSequence;
    var tracks = seq.audioTracks;
    var count = tracks.numTracks;

    var excludeMap = {};
    if (excluded && excluded.length) {
        for (var k = 0; k < excluded.length; k++) {
            var idx = parseInt(excluded[k], 10);
            if (!isNaN(idx)) excludeMap[idx] = 1;
        }
    }

    for (var i = 0; i < count; i++) {
        tracks[i].setMute(excludeMap[i] ? 0 : 1);
    }
}

// Размьючит все аудиодорожки активной секвенции.
function unmuteAllAudio() {
    var seq = app.project.activeSequence;
    var tracks = seq.audioTracks;
    var count = tracks.numTracks;

    for (var i = 0; i < count; i++) {
        tracks[i].setMute(0);
    }
}



////////////// Автоматизация
var BR = $.global.CepJsxBridge;
var cep_data = BR.state.data;

var cep_root = (new File($.fileName)).parent.parent.fsName;

var projectPath = pathHandler(cep_data.projectPath) + '/';
var csvPath = pathHandler(cep_data.csvPath);
var csvName = (new File(csvPath)).name;
var audioPause = cep_data.audioPause;

var langCode = cep_data.languageCode;
var srtNames = ["French", "English", "Spanish", "Portuguese", "Speaker"];
var langMap = {
    en: "English",
    fr: "French",
    es: "Spanish",
    pt: "Portuguese"
};

var voiceTracksIds = [0];
var videoTracksIds = [0];
var soundFxTracksIds = [];

var colorBaseHex = '000000';
var colorHighlightHex = 'FFFFFF';



function testReserve() {
    setInOutFromSelectedAudioClips();
}

function auto_import() {
    importSingleFile(projectPath + "images");
    importSingleFile(projectPath + "normalized");
}

function auto_place_vid_aud() {
    placeItemsOnTimeline(resolveItemsByPaths(['images'], []), 'video', videoTracksIds[0], 0);
    placeItemsOnTimeline(resolveItemsByPaths(['normalized']), 'audio', voiceTracksIds[0], 0);
}

function auto_place_srt(){

    var srtToPlace = [langMap[langCode], langMap['en'], 'Speaker'];
    var missing = [];
    for (var i = 0; i < srtToPlace.length; i++) {
        var name = srtToPlace[i];
        var srtItem = getProjectItemByPath(name + '.srt');
        if (srtItem) {
            placeSrtProjectItemOnNewCaptionTrack(srtItem, 0);
        } else {
            missing.push(name);
        }
    }

    if (missing.length > 0) {
        alert('Не найдены SRT в проекте: ' + missing.join(', '));
    }
}


function auto_move() {
    deselectAllClips()
    
    selectClips(getClipsOnTrack("audio", 0));
    glueSelectedAudioClipsAddGap(audioPause);
    
    selectClips(getClipsOnTrack("audio", 0));
    selectClips(getClipsOnTrack("video", 0));
    AlignImagesToCsvMarks(csvPath);
}

function auto_SrtCreate() {
    deselectAllClips();
    selectClips(getClipsOnTrack("audio", 0));
    collectAudio1TimingsToJson();

    $.sleep(1500);

    for (var i = 0; i < srtNames.length; i++) {
        var filePath = projectPath + srtNames[i] + ".srt";
        var fileObj = new File(filePath);
        if (fileObj.exists) {
            importSingleFile(filePath);
        }
    }
}

function auto_RenderWav() {
    deselectAllClips();
    selectClips(getClipsOnTrack("audio", 0));
    setInOutFromSelectedAudioClips();
    muteAllAudioExcept([0]);

    exportVoiceWav();

    unmuteAllAudio();
}

function testAll() {
    
    //placeItemsOnTimeline([getProjectItemByPath('images')], 'video', 0, 0);
    auto_import();
    auto_place_vid_aud();
    auto_move();
    auto_SrtCreate();
};

/*
const cs = new CSInterface();

const jsxPath = cs.getSystemPath(SystemPath.EXTENSION) + '/jsx/tstScripts.jsx';
const fn   = 'auto_MFA';
const args = ''; 

const cmd = `$.evalFile("${jsxPath}"); ${fn}(${args});`;

cs.evalScript(cmd, function(res){
  console.log('ExtendScript result:', res);
});
*/

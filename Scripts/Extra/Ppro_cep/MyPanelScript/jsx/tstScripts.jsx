//var debugLog = "";
//function log(m){ debugLog += m + "\n"; }

/********************
* ОБЩИЕ УТИЛИТЫ 
********************/
//Проверка что number есть float и выдаем его. Если нет, то выдаем defValue
function checkIfFloat(number, defValue){
    var numberFloat = parseFloat(number);
    if (isNaN(numberFloat)) {
        // Если не число, подставляем дефолтное значение
        alert("введеное значение \""+number+("\" не является float. Использовано значение по умолчанию - \""+defValue+"\""))
        return defValue;
    } else {
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
        } else {
            endTime = referenceClip.end.seconds;
        }
        setClipStartEnd(movingClip, referenceClip.start.seconds, endTime);
    }
}


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
    
            if (i+1 >= clipsA.length) break;
            
            var nextClipA = clipsA[i+1];
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

        var trackA = audioTracks[firstTrackNumber-1];
        var trackB = audioTracks[secondTrackNumber-1];

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
    } catch(e) {
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
    } catch(e) {
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
        var dur  = clip.duration.seconds;
        var newStart = currentTime + GAP_DURATION;
        var newEnd   = newStart + dur;
        setClipStartEnd(clip, newStart, newEnd);
        currentTime = newEnd;
    }

    alert("Клипы перемещены, промежуток между ними: " + GAP_DURATION + " сек");
}


/*--------- Нужно редактировать------*/

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
            } else {
                inQuotes = !inQuotes; // переключаем флаг
            }
        } else if (c === ',' && !inQuotes) {
            // Запятая вне кавычек -> завершение колонки
            result.push(curVal);
            curVal = "";
        } else {
            // Все остальные символы или запятые внутри кавычек
            curVal += c;
        }
    }
    // Добавляем последний накопленный столбец
    result.push(curVal);
    return result;
}

//CSV выровнять картинки


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
   var text = csvText.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
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

   // 4) Считаем общее число строк-данных (без заголовка)
   var totalDataRows = rows.length - 2;

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
function AlignAudioClipsToCsvMarks(targetTrackNumber) {

    // Premiere Pro использует 0‑based индексы треков
    targetTrackNumber = targetTrackNumber - 1;

    /* ===== 0. Проверка активной секвенции ===== */
    var proj = app.project;
    var seq  = proj.activeSequence;
    if (!seq) {
        alert("Нет активной секвенции!");
        return;
    }

    /* ===== 1. Читаем CSV ===== */
    var csvFile = File.openDialog("Выберите CSV файл", "*.csv");
    if (!csvFile || !csvFile.open("r")) {
        alert("Ошибка открытия файла!");
        return;
    }
    var content = csvFile.read();
    csvFile.close();

    /* ===== 2. Извлекаем метки из колонки \"audio\" ===== */
    var data;
    try {
        data = extractCsvMarkers(content, "audio");
    } catch (e) {
        alert(e.message);
        return;
    }
    var markers = data.markers;                // массив номеров строк‑меток (1‑based)

    /* ===== 3. Собираем все выбранные аудио‑клипы ===== */
    var audioTracks      = seq.audioTracks;
    var selectedAllClips = getSelectedClips(audioTracks);

    /* Проверяем корректность номера трека‑приёмника */
    if (targetTrackNumber < 0 || targetTrackNumber >= audioTracks.length) {
        alert("Неверный номер трека: " + (targetTrackNumber + 1));
        return;
    }

    /* ===== 4. Делим на moveClips и targetClips ===== */

    // 4.1  moveClips — выделенные клипы НА указанном треке (их будем двигать)
    var moveClips = getSelectedClips([ audioTracks[targetTrackNumber] ]);

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
        var rowIdx = markers[k];         // номер строки CSV (1‑based)
        var target = targetClips[rowIdx - 1];
        var mover  = moveClips[k];

        if (!target) continue;           // защита от выхода за пределы

        var offset = target.start.seconds - mover.start.seconds;
        var tOff   = new Time();
        tOff.seconds = offset;
        mover.move(tOff);
    }

    alert("Успешно перемещено " + markers.length + " клипов!");
}


function AlignImagesToCsvMarks() {
    /* ===== 0. Активная секвенция ===== */
    var proj = app.project;
    var seq  = proj.activeSequence;
    if (!seq) {
        alert("Нет активной секвенции!");
        return;
    }

    /* ===== 1. Читаем CSV ===== */
    var csvFile = File.openDialog("Выберите CSV файл", "*.csv");
    if (!csvFile || !csvFile.open("r")) {
        alert("Ошибка открытия файла!");
        return;
    }
    var csvContent = csvFile.read();
    csvFile.close();

    /* ===== 2. Извлекаем markers из колонки "images" ===== */
    var data;
    try {
        data = extractCsvMarkers(csvContent, "images");
    } catch (e) {
        alert(e.message);
        return;
    }
    var markers        = data.markers;        // массив номеров строк‑маркеров
    var totalDataRows  = data.totalDataRows;  // всего строк‑данных

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
            "Выделено аудио‑клипов: "       + selectedAudioClips.length
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

    //СТАРАЯ ВЕРСИЯ v1
    /* ===== 5. Выравнивание видео под аудио ===== */ 
    // for (var v = 0; v < selectedVideoClips.length; v++) {
    //     var startMarker = markers[v];
    //     var endMarker   = markers[v + 1];

    //     var audioStart = selectedAudioClips[startMarker - 1];
    //     var audioEnd   = selectedAudioClips[endMarker   - 1];
    //     var videoClip  = selectedVideoClips[v];

    //     var startSec = (v === 0) ? audioStart.start.seconds : audioStart.end.seconds;
    //     var endSec   = audioEnd.end.seconds;

    //     setClipStartEnd(videoClip, startSec, endSec);
    // }


    /* ===== 5. Выравнивание видео под аудио ===== */ 
    for (var v = 0; v < selectedVideoClips.length; v++) {
    var videoClip   = selectedVideoClips[v],
        startSec    = selectedAudioClips[markers[v] - 1].start.seconds,
        endSec,
        nextMarker  = markers[v + 1];

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

/********************
* Список функций для запуска с кнопок: 
********************/

 //zigZagAudioClipsWithOffset(0.4,0.1); //"выравнивание зиг-загом на треках 1 и 2 с паузами" Параметры - 1. пауза после верхних клипов 2. пауза после нижних клипов
 //alignSelectedVideoToAudio(); // "выравнивание выбранных видео клипов по выбранные аудио клипы"
 //glueSelectedAudioClipsAddGap(0.2) // "удалить паузы между клипами и задать фиксированную (допустим 0)" Параметры пауза между клипами

 //AlignImagesToCsvMarks() // "Выравнивание картинок по меткам в csv. Нужно выбрать картинки и аудио клипы."
 //AlignAudioClipsToCsvMarks(4) // "выделите аудио эффекты и аудиоклипы для выравнивания" (1 числовое - выберите трек, на котором находятся аудио-эффекты)


 //alert(debugLog);
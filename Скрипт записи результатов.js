function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents || "{}");
    const results = data.results;

    if (!Array.isArray(results) || results.length === 0) {
      return jsonResponse({ ok: false, error: "Пустой массив results" });
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getActiveSheet();

    const lastCol = Math.max(sheet.getLastColumn(), 4);

    // Строка 1 = чекбоксы
    const row1 = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

    // Строка 2 = заголовки
    const row2 = sheet.getRange(2, 1, 1, lastCol).getValues()[0];

    // Ищем выбранный Timer-столбец
    let selectedTimerCols = [];

    for (let col = 4; col <= lastCol; col++) {
      const checkboxValue = row1[col - 1];
      const headerValue = String(row2[col - 1]).trim();

      if (checkboxValue === true) {
        if (headerValue !== "Timer") {
          return jsonResponse({
            ok: false,
            error: 'Над выбранным чекбоксом в строке 2 должен быть заголовок "Timer"'
          });
        }
        selectedTimerCols.push(col);
      }
    }

    if (selectedTimerCols.length === 0) {
      return jsonResponse({
        ok: false,
        error: "Не выбран столбец Timer (чекбокс в строке 1 над колонкой Timer)"
      });
    }

    if (selectedTimerCols.length > 1) {
      return jsonResponse({
        ok: false,
        error: "Выбрано несколько столбцов Timer. Оставь только один чекбокс."
      });
    }

    const timerCol = selectedTimerCols[0];

    // Считываем существующие данные начиная с 3 строки
    const lastRow = Math.max(sheet.getLastRow(), 2);
    const dataRowsCount = lastRow - 2;

    let existingData = [];
    if (dataRowsCount > 0) {
      existingData = sheet.getRange(3, 1, dataRowsCount, 3).getValues();
    }

    // Карта SKU -> номер строки
    const skuToRowMap = {};
    for (let i = 0; i < existingData.length; i++) {
      const sku = String(existingData[i][1]).trim(); // колонка B
      if (sku) {
        skuToRowMap[sku] = i + 3;
      }
    }

    const rowsToAppend = [];

    for (const item of results) {
      const car = String(item.car || "").trim();
      const sku = String(item.sku || "").trim();
      const brand = String(item.brand || "").trim();
      const timeValue = item.time_s;

      if (!car) {
        continue;
      }

      if (!sku) {
        return jsonResponse({
          ok: false,
          error: `У одной из записей отсутствует SKU: ${car}`
        });
      }

      if (timeValue === "" || timeValue === null || typeof timeValue === "undefined") {
        return jsonResponse({
          ok: false,
          error: `У одной из записей отсутствует time_s: ${car}`
        });
      }

      const existingRow = skuToRowMap[sku];

      if (existingRow) {
        // Обновляем существующую строку
        sheet.getRange(existingRow, 1).setValue(car);         // A
        sheet.getRange(existingRow, 2).setValue(sku);         // B
        sheet.getRange(existingRow, 3).setValue(brand);       // C
        sheet.getRange(existingRow, timerCol).setValue(Number(timeValue)); // D+
      } else {
        // Создаём новую строку
        const newRow = new Array(lastCol).fill("");
        newRow[0] = car;                    // A
        newRow[1] = sku;                    // B
        newRow[2] = brand;                  // C
        newRow[timerCol - 1] = Number(timeValue); // D+

        rowsToAppend.push(newRow);
      }
    }

    if (rowsToAppend.length > 0) {
      const startRow = sheet.getLastRow() + 1;
      sheet.getRange(startRow, 1, rowsToAppend.length, lastCol).setValues(rowsToAppend);
    }

    return jsonResponse({
      ok: true,
      message: "Результаты успешно записаны",
      timerColumn: timerCol,
      count: results.length
    });

  } catch (error) {
    return jsonResponse({
      ok: false,
      error: String(error)
    });
  }
}

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
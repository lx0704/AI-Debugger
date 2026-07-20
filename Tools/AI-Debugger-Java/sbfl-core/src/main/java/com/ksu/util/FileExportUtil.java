package com.ksu.util;

import com.ksu.bean.MethodInfo;
import lombok.AccessLevel;
import lombok.NoArgsConstructor;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.util.CellRangeAddress;
import org.apache.poi.xssf.usermodel.XSSFSheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;

import java.io.FileOutputStream;
import java.io.FileWriter;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

@NoArgsConstructor(access = AccessLevel.PRIVATE)
public class FileExportUtil {

    // ** Reference: Export Data to Excel in Java
    // *? https://www.codejava.net/coding/java-code-example-to-export-data-from-database-to-excel-file
    // */

    public static void xlsExport(String fileName, List<Map.Entry<String, MethodInfo>> dataList) throws IOException {
        try (XSSFWorkbook workbook = new XSSFWorkbook()) {
            XSSFSheet sheet = workbook.createSheet("caluclatedSuspicion");

            writeHeaderLine(sheet);
            writeDataLines(dataList, sheet);
            beautifyColumns(sheet);

            FileOutputStream outputStream = new FileOutputStream(fileName);
            workbook.write(outputStream);
        }
    }

    public static void csvExport(String fileName, List<Map.Entry<String, MethodInfo>> dataList) throws IOException {
        try (FileWriter writer = new FileWriter(fileName)) {
            // Write header
            writer.append("Method Name,Tarantula Suspicion,SBI Suspicion,Jaccard Suspicion,Ochai Suspicion,Ample,Russel Rao,Dice,Wong1,Wong2,Dstar2,Kulczynski1,Sorensen Dice,GP03,GP13\n");

            // Write data rows
            for (Map.Entry<String, MethodInfo> entry : dataList) {
                MethodInfo info = entry.getValue();
                writer.append(entry.getKey())
                        .append(',')
                        .append(String.valueOf(info.getSuspiciousnessTarantula()))
                        .append(',')
                        .append(String.valueOf(info.getSuspiciousnessSbi()))
                        .append(',')
                        .append(String.valueOf(info.getSuspiciousnessJaccard()))
                        .append(',')
                        .append(String.valueOf(info.getSuspiciousnessOchiai()))
                        .append(',')
                        .append(String.valueOf(info.getAmple()))
                        .append(',')
                        .append(String.valueOf(info.getRusselRao()))
                        .append(',')
                        .append(String.valueOf(info.getDice()))
                        .append(",")
                        .append(String.valueOf(info.getWong1()))
                        .append(',')
                        .append(String.valueOf(info.getWong2()))
                        .append(',')
                        .append(String.valueOf(info.getDstar2()))
                        .append(',')
                        .append(String.valueOf(info.getKulczynski1()))
                        .append(',')
                        .append(String.valueOf(info.getSorensenDice()))
                        .append(',')
                        .append(String.valueOf(info.getGp03()))
                        .append(',')
                        .append(String.valueOf(info.getGp13()))
                        .append('\n');
            }
        }
    }

    private static void beautifyColumns(XSSFSheet sheet) {

        // *? REF: https://stackoverflow.com/a/59718764
        // ** Set Fixed Width for Column
        sheet.setColumnWidth(0, 90 * 256);

        // *? REF: https://www.baeldung.com/java-apache-poi-expand-columns
        // ** Add Auto Width on All Columns
        sheet.autoSizeColumn(1);
        sheet.autoSizeColumn(2);
        sheet.autoSizeColumn(3);
        sheet.autoSizeColumn(4);
        sheet.autoSizeColumn(5);
        sheet.autoSizeColumn(6);
        sheet.autoSizeColumn(7);
        sheet.autoSizeColumn(8);
        sheet.autoSizeColumn(9);
        sheet.autoSizeColumn(10);
        sheet.autoSizeColumn(11);
        sheet.autoSizeColumn(12);
        sheet.autoSizeColumn(13);
        sheet.autoSizeColumn(14);
        sheet.createFreezePane(0, 1);

        // *? REF: https://stackoverflow.com/questions/77938769/how-to-add-filters-for-specific-columns-using-apache-poi
        sheet.setAutoFilter(CellRangeAddress.valueOf("A1:O1"));
    }

    private static void writeHeaderLine(XSSFSheet sheet) {

        Row headerRow = sheet.createRow(0);

        Cell headerCell = headerRow.createCell(0);
        headerCell.setCellValue("Method Name");

        headerCell = headerRow.createCell(1);
        headerCell.setCellValue("Tarantula");

        headerCell = headerRow.createCell(2);
        headerCell.setCellValue("SBI");

        headerCell = headerRow.createCell(3);
        headerCell.setCellValue("Jaccard");

        headerCell = headerRow.createCell(4);
        headerCell.setCellValue("Ochai");

        headerCell = headerRow.createCell(5);
        headerCell.setCellValue("Ample");

        headerCell = headerRow.createCell(6);
        headerCell.setCellValue("Russel Rao");

        headerCell = headerRow.createCell(7);
        headerCell.setCellValue("Dice");

        headerCell = headerRow.createCell(8);
        headerCell.setCellValue("Wong1");

        headerCell = headerRow.createCell(9);
        headerCell.setCellValue("Wong2");

        headerCell = headerRow.createCell(10);
        headerCell.setCellValue("Dstar2");

        headerCell = headerRow.createCell(11);
        headerCell.setCellValue("Kulczynski1");

        headerCell = headerRow.createCell(12);
        headerCell.setCellValue("Sorensen Dice");

        headerCell = headerRow.createCell(13);
        headerCell.setCellValue("GP03");

        headerCell = headerRow.createCell(14);
        headerCell.setCellValue("GP13");
    }

    private static void writeDataLines(List<Map.Entry<String, MethodInfo>> dataList,
                                       XSSFSheet sheet) {
        AtomicInteger rowCount = new AtomicInteger(1);

        dataList.forEach(entry -> {
            double tarantulaSuspicion = entry.getValue().getSuspiciousnessTarantula();
            double sbiSuspicion = entry.getValue().getSuspiciousnessSbi();
            double jaccardSuspicion = entry.getValue().getSuspiciousnessJaccard();
            double ochaiSuspicion = entry.getValue().getSuspiciousnessOchiai();

            double ampleSuspicion = entry.getValue().getAmple();
            double russelRaoSuspicion = entry.getValue().getRusselRao();
            double diceSuspicion = entry.getValue().getDice();
            double wong1Suspicion = entry.getValue().getWong1();
            double wong2Suspicion = entry.getValue().getWong2();
            double dstar2Suspicion = entry.getValue().getDstar2();
            double kulczynski1 = entry.getValue().getKulczynski1();
            double sorensenDice = entry.getValue().getSorensenDice();
            double gp03 = entry.getValue().getGp03();
            double gp13 = entry.getValue().getGp13();

            Row row = sheet.createRow(rowCount.getAndIncrement());

            int columnCount = 0;
            Cell cell = row.createCell(columnCount++);
            cell.setCellValue(entry.getKey());

            cell = row.createCell(columnCount++);
            cell.setCellValue(tarantulaSuspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(sbiSuspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(jaccardSuspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(ochaiSuspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(ampleSuspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(russelRaoSuspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(diceSuspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(wong1Suspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(wong2Suspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(dstar2Suspicion);

            cell = row.createCell(columnCount++);
            cell.setCellValue(kulczynski1);

            cell = row.createCell(columnCount++);
            cell.setCellValue(sorensenDice);

            cell = row.createCell(columnCount++);
            cell.setCellValue(gp03);

            cell = row.createCell(columnCount++);
            cell.setCellValue(gp13);

        });

    }

}
package com.ksu.util;

import com.ksu.bean.MethodInfo;
import lombok.AccessLevel;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

@NoArgsConstructor(access = AccessLevel.PRIVATE)
public class SuspicionProcessor {

    public static double calculateTarantula(double ef, double ep, double nf, double np) {
        double failRatio = safeDiv(ef, ef + nf);
        double passRatio = safeDiv(ep, ep + np);
        return safeDiv(failRatio, failRatio + passRatio);
    }

    public static double calculateSbi(double ef, double ep) {
        return safeDiv(ef, ef + ep);
    }

    public static double calculateJaccard(double ef, double ep, double nf) {
        return safeDiv(ef, nf + ep);
    }

    public static double calculateOchiai(double ef, double ep, double nf) {
        return ef / Math.sqrt(nf * (ef + ep));
    }

    public static double calculateAmple(double ef, double ep, double nf, double np) {
        return Math.abs(safeDiv(ef, ef + nf) - safeDiv(ep, ep + np));
    }

    public static double calculateRusselRao(double ef, double nf, double np) {
        return safeDiv(ef, nf + np);
    }

    public static double calculateDice(double ef, double ep, double nf) {
        return safeDiv(2 * ef, nf + ep);
    }

    public static double calculateWong1(double ef) {
        return Math.abs(ef);
    }

    public static double calculateWong2(double ef, double ep) {
        return Math.abs(ef - ep);
    }


    public static double calculateDstar2(double ef, double ep, double nf, double np) {
        return safeDiv(Math.pow(ef, 2), ep + nf + np);
    }

    public static double calculateKulczynski1(double ef, double ep, double nf) {
        return safeDiv(ef, nf + ep);
    }

    public static double calculateSorensenDice(double ef, double ep, double nf) {
        return safeDiv(2 * ef, 2 * ef + ep + nf);
    }

    public static double calculateGP03(double ef, double ep) {
        return Math.sqrt(Math.abs(Math.pow(ef, 2) - Math.sqrt(ep)));
    }

    public static double calculateGP13(double ef, double ep) {
        return ef * (1 + safeDiv(1, 2 * ep + ef));
    }

    public static List<Map.Entry<String, MethodInfo>> sortSuspicion(Map<String, MethodInfo> data) {
        List<Map.Entry<String, MethodInfo>> dataList = new ArrayList<>(data.entrySet());

        // ** Sort the data in descending order of Tarantula, SBI, Jaccard, Ochai
        dataList.sort(Comparator
                .comparingDouble((Map.Entry<String, MethodInfo> entry) -> entry.getValue().getSuspiciousnessTarantula())
                .reversed()
                .thenComparing(Comparator.comparingDouble((Map.Entry<String, MethodInfo> entry) -> entry.getValue().getSuspiciousnessSbi())
                        .reversed())
                .thenComparing(Comparator.comparingDouble((Map.Entry<String, MethodInfo> entry) -> entry.getValue().getSuspiciousnessJaccard())
                        .reversed())
                .thenComparing(Comparator.comparingDouble((Map.Entry<String, MethodInfo> entry) -> entry.getValue().getSuspiciousnessOchiai())
                        .reversed())
        );
        return dataList;
    }

    private static double safeDiv(double numerator, double denominator) {
        return denominator == 0 ? 0.0 : numerator / denominator;
    }


}
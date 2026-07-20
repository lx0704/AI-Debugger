package com.ksu.util;

import com.ksu.bean.MethodInfo;
import lombok.AccessLevel;
import lombok.NoArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@NoArgsConstructor(access = AccessLevel.PRIVATE)
public class Analyzer {

    static Map<String, MethodInfo> methodMap = new HashMap<>();

    public static Map<String, MethodInfo> analyzeFolder(File folder, int failCount) {

        File[] listOfFiles = folder.listFiles((dir, name) -> name.toLowerCase().endsWith(".txt"));


        int flunkCount = 0;
        int totalFailedTests = 0;
        int totalPassedTests = 0;

        if (listOfFiles != null && listOfFiles.length > 0) {
            for (File file : listOfFiles) {
                if (file.isFile()) {
                    try {
                        List<String> lines = Files.readAllLines(Paths.get(file.getPath()));
                        if (!lines.isEmpty()) {
                            String firstLine = lines.get(0);
                            String[] parts = firstLine.split(" ");
                            if (parts.length == 2) {
                                String testName = parts[0];
                                boolean testResult = Boolean.parseBoolean(parts[1]);
                                System.out.println("Reading File:- TestName: {}" + testName + ", testResult: " + testResult);

                                //** Manually Updating the First 200 Files to False irrespective of their initial value */
                                if (flunkCount++ < failCount) {
                                    System.out.println("Updating TestResult with Failure. prevVal:{}" + testResult + ",  currentVal:{}" + false);
                                    testResult = false;
                                }

                                //** Increment Total Pass and Fail
                                if (testResult) {
                                    totalPassedTests++;
                                } else {
                                    totalFailedTests++;
                                }

                                constructAndUpdateMethodDetails(lines, testName, testResult);
                            }
                        }
                    } catch (IOException e) {
                        System.out.println("Error reading File.");
                    }
                }
            }

            // ** Compute Suspicious Formulas
            computeSBFLForEachMethod(totalPassedTests, totalFailedTests);

            return methodMap;

        } else {
            System.out.println("The directory is empty or does not exist.");
        }
        return Collections.emptyMap();
    }

    private static void computeSBFLForEachMethod(int totalPassedTests, int totalFailedTests) {
        methodMap.forEach((methodName, methodInfo) -> {
            methodInfo.setSuspiciousnessTarantula(SuspicionProcessor.calculateTarantula(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures(), totalFailedTests, totalPassedTests));

            methodInfo.setSuspiciousnessSbi(SuspicionProcessor.calculateSbi(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures()));

            methodInfo.setSuspiciousnessJaccard(SuspicionProcessor.calculateJaccard(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures(), totalFailedTests));

            methodInfo.setSuspiciousnessOchiai(SuspicionProcessor.calculateOchiai(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures(), totalFailedTests));

            methodInfo.setAmple(SuspicionProcessor.calculateAmple(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures(), totalFailedTests, totalPassedTests));

            methodInfo.setRusselRao(SuspicionProcessor.calculateRusselRao(
                    methodInfo.getMethodFailures(), totalFailedTests, totalPassedTests));

            methodInfo.setDice(SuspicionProcessor.calculateDice(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures(), totalFailedTests));

            methodInfo.setWong1(SuspicionProcessor.calculateWong1(methodInfo.getMethodFailures()));

            methodInfo.setWong2(SuspicionProcessor.calculateWong2(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures()));

            methodInfo.setDstar2(SuspicionProcessor.calculateDstar2(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures(), totalFailedTests, totalPassedTests));

            methodInfo.setKulczynski1(SuspicionProcessor.calculateKulczynski1(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures(), totalFailedTests));

            methodInfo.setSorensenDice(SuspicionProcessor.calculateSorensenDice(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures(), totalFailedTests));

            methodInfo.setGp03(SuspicionProcessor.calculateGP03(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures()));

            methodInfo.setGp13(SuspicionProcessor.calculateGP13(methodInfo.getMethodPasses(),
                    methodInfo.getMethodFailures()));
        });
    }

    private static void constructAndUpdateMethodDetails(List<String> lines, String testName, boolean testResult) {
        lines.stream().skip(1).forEach(methodName -> {

            // ** Constructing DataStructure */
            methodMap.compute(methodName, (k, v) -> {
                if (v == null) {
                    v = new MethodInfo(testName);
                }
                if (testResult) {
                    v.setMethodFailures(v.getMethodFailures() + 1);
                } else {
                    v.setMethodPasses(v.getMethodPasses() + 1);
                }
                return v;
            });

        });
    }
}
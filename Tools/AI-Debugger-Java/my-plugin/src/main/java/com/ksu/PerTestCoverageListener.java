package com.ksu;

import org.jacoco.core.analysis.Analyzer;
import org.jacoco.core.analysis.CoverageBuilder;
import org.jacoco.core.analysis.IClassCoverage;
import org.jacoco.core.analysis.IMethodCoverage;
import org.jacoco.core.data.ExecutionDataStore;
import org.jacoco.core.data.SessionInfoStore;
import org.jacoco.core.runtime.IRuntime;
import org.jacoco.core.runtime.LoggerRuntime;
import org.jacoco.core.runtime.RuntimeData;
import org.junit.runner.Description;
import org.junit.runner.Result;
import org.junit.runner.notification.Failure;
import org.junit.runner.notification.RunListener;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

public class PerTestCoverageListener extends RunListener {

    public PerTestCoverageListener() {
        System.out.println("*** PerTestCoverageListener CONSTRUCTOR CALLED ***");
        System.err.println("*** PerTestCoverageListener CONSTRUCTOR CALLED ***");
    }

    private static final String COVERAGE_DIR = "target/per-test-coverage/";
    private final Map<String, Boolean> testResults = new HashMap<>();
    private IRuntime runtime;
    private RuntimeData data;
    private String currentTest;

    @Override
    public void testRunStarted(Description description) throws Exception {

        // Create output directory
        new File(COVERAGE_DIR).mkdirs();

        // Initialize JaCoCo runtime
        runtime = new LoggerRuntime();
        data = new RuntimeData();
        runtime.startup(data);

        System.out.println("JaCoCo method-level coverage collection started");
        System.out.println("Output directory: " + new File(COVERAGE_DIR).getAbsolutePath());
    }

    @Override
    public void testStarted(Description description) throws Exception {
        System.out.println("*** TEST STARTED: " + description.getDisplayName() + " ***");
        System.err.println("*** TEST STARTED: " + description.getDisplayName() + " ***");

        currentTest = description.getClassName() + "." + description.getMethodName();

        // Reset coverage data for this test
        data.reset();

        System.out.println("Starting test: " + currentTest);
    }

    @Override
    public void testFinished(Description description) throws Exception {
        // Mark test as passed (will be overridden if failed)
        testResults.putIfAbsent(currentTest, true);

        // Collect and save coverage data for this test
        collectAndSaveCoverage();

        System.out.println("Finished test: " + currentTest);
    }

    @Override
    public void testFailure(Failure failure) throws Exception {
        // Mark test as failed
        String testName = failure.getDescription().getClassName() + "." + failure.getDescription().getMethodName();
        testResults.put(testName, false);
        System.out.println("Test failed: " + testName + " - " + failure.getMessage());
    }

    @Override
    public void testRunFinished(Result result) throws Exception {
        if (runtime != null) {
            runtime.shutdown();
        }
        System.out.println("Coverage collection completed. Files in: " + new File(COVERAGE_DIR).getAbsolutePath());
        System.out.println("Total tests run: " + result.getRunCount());
        System.out.println("Failures: " + result.getFailureCount());
    }

    private void collectAndSaveCoverage() {
        try {
            final ExecutionDataStore executionData = new ExecutionDataStore();
            final SessionInfoStore sessionInfos = new SessionInfoStore();

            data.collect(executionData, sessionInfos, false);

            // Analyze coverage
            final CoverageBuilder coverageBuilder = new CoverageBuilder();
            final Analyzer analyzer = new Analyzer(executionData, coverageBuilder);

            // Analyze all class files
            File classesDir = new File("target/classes");
            if (classesDir.exists() && classesDir.isDirectory()) {
                analyzer.analyzeAll(classesDir);
            } else {
                System.err.println("Classes directory not found: " + classesDir.getAbsolutePath());
                return;
            }

            // Save method-level coverage data
            saveMethodCoverageData(currentTest, coverageBuilder);

        } catch (IOException e) {
            System.err.println("Error collecting coverage for test " + currentTest + ": " + e.getMessage());
            e.printStackTrace();
        }
    }

    private void saveMethodCoverageData(String testName, CoverageBuilder coverageBuilder) {
        try {
            String fileName = COVERAGE_DIR + sanitizeFileName(testName) + ".txt";
            FileWriter writer = new FileWriter(fileName);

            // First line: test name and result
            Boolean testPassed = testResults.get(testName);
            if (testPassed == null) {
                testPassed = true; // Default to true if not found
            }
            writer.write(testName + " " + testPassed.toString().toLowerCase() + "\n");
            writer.write(coverageBuilder.toString());

            // Write covered methods
            for (final IClassCoverage classCoverage : coverageBuilder.getClasses()) {
                String className = classCoverage.getName(); // Keep the slash format: org/example/Class

                // Skip test classes - only analyze production code
                if (isTestClass(className)) {
                    continue;
                }

                // Iterate through methods
                for (final IMethodCoverage methodCoverage : classCoverage.getMethods()) {
                    String methodName = methodCoverage.getName();
                    String methodDesc = methodCoverage.getDesc();

                    // Format: className:methodName:methodDescriptor
                    String methodSignature = className + ":" + methodName + ":" + methodDesc;
                    writer.write(methodSignature + "\n");

                }
            }

            writer.close();
            System.out.println("Saved method coverage data: " + fileName);

        } catch (IOException e) {
            System.err.println("Error saving method coverage data for " + testName + ": " + e.getMessage());
            e.printStackTrace();
        }
    }

    private boolean isTestClass(String className) {
        // Convert slash format to dot format for checking
        String dotClassName = className.replace('/', '.');
        return dotClassName.toLowerCase().contains("test") ||
                dotClassName.toLowerCase().endsWith("tests") ||
                dotClassName.toLowerCase().contains("mock");
    }

    private String sanitizeFileName(String testName) {
        return testName.replace(".", "_")
                .replace("#", "_")
                .replace("/", "_")
                .replace("\\", "_")
                .replace(":", "_")
                .replace(" ", "_");
    }
}
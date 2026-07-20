package com.ksu;

import org.apache.maven.plugin.AbstractMojo;
import org.apache.maven.plugin.MojoExecutionException;
import org.apache.maven.plugins.annotations.LifecyclePhase;
import org.apache.maven.plugins.annotations.Mojo;
import org.apache.maven.plugins.annotations.Parameter;
import org.apache.maven.project.MavenProject;
import org.apache.maven.settings.Settings;
import org.apache.maven.shared.invoker.*;

import java.io.File;
import java.io.IOException;
import java.util.Collections;
import java.util.Properties;

@Mojo(name = "jacocoSurefireCoverage", defaultPhase = LifecyclePhase.TEST)
public class JacocoMojo extends AbstractMojo {

    @Parameter(defaultValue = "${project}", readonly = true, required = true)
    private MavenProject project;

    @Parameter(defaultValue = "${settings}", readonly = true)
    private Settings settings;

    @Parameter(property = "skipTests", defaultValue = "false")
    private boolean skipTests;

    @Parameter(property = "testFailureIgnore", defaultValue = "true")
    private boolean testFailureIgnore;

    @Parameter(property = "jacocoDestFile")
    private String jacocoDestFile;

    public void execute() throws MojoExecutionException {
        if (skipTests) {
            getLog().info("Tests are skipped.");
            return;
        }

        try {
            // Execute the plugin sequence
            executeJaCoCoAndTests();
        } catch (Exception e) {
            throw new MojoExecutionException("Failed to execute JaCoCo and tests", e);
        }
    }

    private void executeJaCoCoAndTests() throws MavenInvocationException {
        getLog().info("Starting JaCoCo and Surefire execution sequence");

//        // Step 1: Clean to ensure fresh start
//        executeClean();
//
//        // Step 2: Compile main sources
//        executeCompile();

        // Step 3: Prepare JaCoCo agent (CRITICAL: Must be before test-compile)
        executeJaCoCoPrepareAgent();

        // Step 4: Compile test sources
//        executeTestCompile();

        // Step 5: Run tests with Surefire
        executeSurefireTests();

        getLog().info("JaCoCo and Surefire execution completed successfully");
    }

    private void executeClean() throws MavenInvocationException {
        getLog().info("=== Cleaning target directory ===");

        InvocationRequest request = new DefaultInvocationRequest();
        request.setPomFile(new File(project.getBasedir(), "pom.xml"));
        request.setGoals(Collections.singletonList("clean"));

        executeWithInvoker(request, "Clean");
    }

    private void executeCompile() throws MavenInvocationException {
        getLog().info("=== Compiling main sources ===");

        InvocationRequest request = new DefaultInvocationRequest();
        request.setPomFile(new File(project.getBasedir(), "pom.xml"));
        request.setGoals(Collections.singletonList("compile"));

        executeWithInvoker(request, "Compile");
    }

    private void executeJaCoCoPrepareAgent() throws MavenInvocationException {
        getLog().info("=== Executing JaCoCo prepare-agent ===");

        InvocationRequest request = new DefaultInvocationRequest();
        request.setPomFile(new File(project.getBasedir(), "pom.xml"));
        request.setGoals(Collections.singletonList("org.jacoco:jacoco-maven-plugin:0.8.11:prepare-agent"));

        // Set JaCoCo properties - CRITICAL FIXES
        Properties props = new Properties();

        // Determine destFile path
        String destFile = jacocoDestFile != null ? jacocoDestFile :
                "${project.build.directory}/jacoco-per-test.exec";

        props.setProperty("jacoco.destFile", destFile);
        props.setProperty("jacoco.append", "false");
        props.setProperty("jacoco.sessionId", getCurrentTimestamp());

        // CRITICAL: Set property name for argLine (this is what was missing!)
        props.setProperty("jacoco.propertyName", "jacocoArgLine");

        request.setProperties(props);

        executeWithInvoker(request, "JaCoCo prepare-agent");
    }

    private void executeTestCompile() throws MavenInvocationException {
        getLog().info("=== Compiling test sources ===");

        InvocationRequest request = new DefaultInvocationRequest();
        request.setPomFile(new File(project.getBasedir(), "pom.xml"));
        request.setGoals(Collections.singletonList("test-compile"));

        executeWithInvoker(request, "Test compilation");
    }

    private void executeSurefireTests() throws MavenInvocationException {
        getLog().info("=== Executing Surefire tests with listener ===");

        InvocationRequest request = new DefaultInvocationRequest();
        request.setPomFile(new File(project.getBasedir(), "pom.xml"));
        request.setGoals(Collections.singletonList("org.apache.maven.plugins:maven-surefire-plugin:3.0.0:test"));

        // Set Surefire properties
        Properties props = new Properties();
        props.setProperty("maven.test.failure.ignore", String.valueOf(testFailureIgnore));
        props.setProperty("forkCount", "1");
        props.setProperty("reuseForks", "false");

//        // CRITICAL FIX: Add JaCoCo argLine (this was the main missing piece!)
        props.setProperty("argLine", "${jacocoArgLine}");

        // CRITICAL FIX: Configure listener properly for Surefire 3.0+
        String listenerClass = "com.ksu.PerTestCoverageListener";
        getLog().info("*** Configuring test listener: " + listenerClass + " ***");

        // Method 2: System property approach
        props.setProperty("listener", listenerClass);

        // Configure listener through various system properties
        props.setProperty("systemProperties.listener", listenerClass);
        props.setProperty("systemProperties.junit.platform.listeners.enable", "true");
        props.setProperty("systemProperties.junit.jupiter.extensions.autodetection.enabled", "true");

        // For JUnit 4 compatibility
        props.setProperty("systemProperties.junit4.listeners", listenerClass);

        // Additional debug properties
        props.setProperty("systemProperties.surefire.listener.debug", "true");


        // Additional Surefire configurations
        props.setProperty("surefire.useSystemClassLoader", "false");
        props.setProperty("surefire.useManifestOnlyJar", "false");

        // Enable verbose output to see listener loading
        props.setProperty("surefire.printSummary", "true");

        request.setProperties(props);

        executeWithInvoker(request, "Surefire tests");
    }

    private void executeWithInvoker(InvocationRequest request, String stepName)
            throws MavenInvocationException {

        Invoker invoker = new DefaultInvoker();

        // Set Maven home
        invoker.setMavenHome(new File("C:\\work\\apache-maven-3.9.11"));
        invoker.setWorkingDirectory(project.getBasedir());

//        // CRITICAL FIX: Set clean environment variables
//        Map<String, String> envVars = new HashMap<>();
//        envVars.put("MAVEN_OPTS", "-Xmx1024m"); // Clean MAVEN_OPTS
//        request.setEnvironmentVariables(envVars);

        // Configure output handlers with listener detection
        invoker.setOutputHandler(new InvocationOutputHandler() {
            @Override
            public void consumeLine(String line) throws IOException {
                // Highlight listener-related messages
                if (line.contains("PerTestCoverageListener") ||
                        line.contains("listener") ||
                        line.contains("Listener") ||
                        line.contains("TestExecutionListener")) {
                    getLog().info("*** LISTENER ACTIVITY ***: " + stepName + ": " + line);
                } else if (line.contains("jacocoArgLine") || line.contains("jacoco")) {
                    getLog().info("*** JACOCO ACTIVITY ***: " + stepName + ": " + line);
                } else if (!line.contains("Downloading") && !line.contains("Downloaded")) {
                    getLog().info(stepName + ": " + line);
                }
            }
        });

        invoker.setErrorHandler(new InvocationOutputHandler() {
            @Override
            public void consumeLine(String line) throws IOException {
                if (line.contains("jdwp") || line.contains("JDWP")) {
                    getLog().error("*** DEBUG PORT ISSUE ***: " + line);
                } else {
                    getLog().error(stepName + " Error: " + line);
                }
            }
        });

        getLog().info("Executing " + stepName + " in: " + project.getBasedir());
        getLog().info("Goals: " + request.getGoals());
        if (request.getProperties() != null && !request.getProperties().isEmpty()) {
            getLog().info("Properties: " + request.getProperties());
        }

        InvocationResult result = invoker.execute(request);

        if (result.getExitCode() != 0) {
            if (testFailureIgnore && stepName.contains("test")) {
                getLog().warn(stepName + " failed with exit code: " + result.getExitCode() +
                        " (ignored due to testFailureIgnore=true)");
            } else {
                throw new RuntimeException(stepName + " execution failed with exit code: " +
                        result.getExitCode());
            }
        }

        getLog().info(stepName + " completed successfully");
    }

    private String getCurrentTimestamp() {
        return java.time.Instant.now().toString();
    }

}
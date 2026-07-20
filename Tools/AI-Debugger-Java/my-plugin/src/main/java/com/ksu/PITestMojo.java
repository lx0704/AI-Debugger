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
import java.util.Arrays;


@Mojo(name = "PITest", defaultPhase = LifecyclePhase.TEST)
public class PITestMojo extends AbstractMojo {

    @Parameter(defaultValue = "${project}", readonly = true, required = true)
    private MavenProject project;

    @Parameter(defaultValue = "${settings}", readonly = true)
    private Settings settings;

    public void execute() throws MojoExecutionException {
        try {
            runPITestWithInvoker();
        } catch (Exception e) {
            throw new MojoExecutionException("Failed to execute PITest with invoker", e);
        }
    }

    private void runPITestWithInvoker() throws MavenInvocationException {
        InvocationRequest request = new DefaultInvocationRequest();
        request.setPomFile(new File(project.getBasedir(), "pom.xml"));
        request.setGoals(Arrays.asList(
//                "clean",
                "test-compile",
                "org.pitest:pitest-maven:mutationCoverage"
        ));

//        // Set properties
//        Properties props = new Properties();
//        props.setProperty("skipTests", "true");
//        props.setProperty("maven.test.skip", "false"); // Allow test compilation
//        props.setProperty("pit.reportDir", project.getBuild().getDirectory() + "/pit-reports");
//        props.setProperty("pit.targetClasses", "com.yourpackage.*"); // Adjust as needed
//        props.setProperty("pit.targetTests", "com.yourpackage.*Test"); // Adjust as needed
//        props.setProperty("pit.outputFormats", "HTML,XML");
//        request.setProperties(props);

        // Configure invoker
        Invoker invoker = new DefaultInvoker();
        invoker.setMavenHome(new File("C:\\work\\apache-maven-3.9.11"));
        invoker.setWorkingDirectory(project.getBasedir());

        // Custom output handler
        invoker.setOutputHandler(new InvocationOutputHandler() {
            @Override
            public void consumeLine(String line) throws IOException {
                getLog().info("Maven: " + line);
            }
        });

        invoker.setErrorHandler(new InvocationOutputHandler() {
            @Override
            public void consumeLine(String line) throws IOException {
                getLog().error("Maven Error: " + line);
            }
        });

        getLog().info("Invoking Maven PITest in: " + project.getBasedir());

        InvocationResult result = invoker.execute(request);

        if (result.getExitCode() != 0) {
            throw new RuntimeException("Maven PITest execution failed with exit code: " +
                    result.getExitCode());
        }

        getLog().info("PITest completed successfully via Maven Invoker");
    }
}
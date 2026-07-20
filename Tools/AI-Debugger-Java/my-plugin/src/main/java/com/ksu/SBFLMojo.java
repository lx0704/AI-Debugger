package com.ksu;

import org.apache.maven.plugin.AbstractMojo;
import org.apache.maven.plugin.MojoExecutionException;
import org.apache.maven.plugin.MojoFailureException;
import org.apache.maven.plugins.annotations.LifecyclePhase;
import org.apache.maven.plugins.annotations.Mojo;
import org.apache.maven.plugins.annotations.Parameter;
import org.apache.maven.project.MavenProject;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@Mojo(name = "SBFL", defaultPhase = LifecyclePhase.TEST)
public class SBFLMojo extends AbstractMojo {

    @Parameter(defaultValue = "${project}", required = true, readonly = true)
    private MavenProject project;
    private File outputDirectory;
    private Runner runner;

    @Override
    public void execute() throws MojoExecutionException, MojoFailureException {
        runner = new Runner();
        try {
            getLog().info("outputDirectory" + project.getBuild().getDirectory());
            try {
                Path coverageDir = Paths.get(project.getBuild().getDirectory(), "per-test-coverage");
                if (Files.notExists(coverageDir)) {
                    Files.createDirectories(coverageDir);
                    getLog().info("Created directory: " + coverageDir.toAbsolutePath());
                } else {
                    getLog().info("Directory already exists: " + coverageDir.toAbsolutePath());
                }
            } catch (IOException e) {
                getLog().error("Failed to create per-test-coverage directory", e);
            }
            runner.runSbfl(project.getBuild().getDirectory() + "/per-test-coverage", 0);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
}

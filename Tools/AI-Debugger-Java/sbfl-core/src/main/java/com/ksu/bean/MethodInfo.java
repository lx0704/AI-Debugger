package com.ksu.bean;

public class MethodInfo {
    private String name;
    private int methodPasses;
    private int methodFailures;

    private double suspiciousnessTarantula;
    private double suspiciousnessSbi;
    private double suspiciousnessJaccard;
    private double suspiciousnessOchiai;

    private double ample;
    private double russelRao;
    private double dice;
    private double wong1;
    private double wong2;
    private double dstar2;
    private double kulczynski1;
    private double sorensenDice;
    private double gp03;
    private double gp13;

    public double getSuspiciousnessJaccard() {
        return suspiciousnessJaccard;
    }

    public void setSuspiciousnessJaccard(double suspiciousnessJaccard) {
        this.suspiciousnessJaccard = suspiciousnessJaccard;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public int getMethodPasses() {
        return methodPasses;
    }

    public void setMethodPasses(int methodPasses) {
        this.methodPasses = methodPasses;
    }

    public int getMethodFailures() {
        return methodFailures;
    }

    public void setMethodFailures(int methodFailures) {
        this.methodFailures = methodFailures;
    }

    public double getSuspiciousnessTarantula() {
        return suspiciousnessTarantula;
    }

    public void setSuspiciousnessTarantula(double suspiciousnessTarantula) {
        this.suspiciousnessTarantula = suspiciousnessTarantula;
    }

    public double getSuspiciousnessSbi() {
        return suspiciousnessSbi;
    }

    public void setSuspiciousnessSbi(double suspiciousnessSbi) {
        this.suspiciousnessSbi = suspiciousnessSbi;
    }

    public double getSuspiciousnessOchiai() {
        return suspiciousnessOchiai;
    }

    public void setSuspiciousnessOchiai(double suspiciousnessOchiai) {
        this.suspiciousnessOchiai = suspiciousnessOchiai;
    }

    public double getRusselRao() {
        return russelRao;
    }

    public void setRusselRao(double russelRao) {
        this.russelRao = russelRao;
    }

    public double getAmple() {
        return ample;
    }

    public void setAmple(double ample) {
        this.ample = ample;
    }

    public double getDice() {
        return dice;
    }

    public void setDice(double dice) {
        this.dice = dice;
    }

    public double getWong1() {
        return wong1;
    }

    public void setWong1(double wong1) {
        this.wong1 = wong1;
    }

    public double getWong2() {
        return wong2;
    }

    public void setWong2(double wong2) {
        this.wong2 = wong2;
    }

    public double getDstar2() {
        return dstar2;
    }

    public void setDstar2(double dstar2) {
        this.dstar2 = dstar2;
    }

    public double getKulczynski1() {
        return kulczynski1;
    }

    public void setKulczynski1(double kulczynski1) {
        this.kulczynski1 = kulczynski1;
    }

    public double getSorensenDice() {
        return sorensenDice;
    }

    public void setSorensenDice(double sorensenDice) {
        this.sorensenDice = sorensenDice;
    }

    public double getGp03() {
        return gp03;
    }

    public void setGp03(double gp03) {
        this.gp03 = gp03;
    }

    public double getGp13() {
        return gp13;
    }

    public void setGp13(double gp13) {
        this.gp13 = gp13;
    }

    public MethodInfo(String name) {
        this.name = name;
        methodPasses = 0;
        methodFailures = 0;
    }


}
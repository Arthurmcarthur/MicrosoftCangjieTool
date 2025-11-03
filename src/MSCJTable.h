#ifndef MSCJTABLE_H
#define MSCJTABLE_H

#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include "MSCJKanji.hpp"
#include "KanjiBlockValueStrategy.hpp"
#include <QObject>
#include <QApplication>
#include <QDir>
#include <QDebug>
#include <QFile>
#include <QTemporaryDir>
#include <QThread>
#include <QtConcurrent>
#include <QFuture>
#include <QFileInfo>
#include <QStringConverter>


class MSCJTable : public QObject
{
    Q_OBJECT
public:
    explicit MSCJTable(QObject *parent = nullptr);
    enum ExitCode {
        installSuccess = 1,
        success = 0,
        hkscsFileNotFound = -1,
        codeChartNotFound = -2,
        codeChartFormatError = -3,
        thereArePhrasesInTheCodeChart = -4,
        cjCodeLengthError = -5,
        cjCodeError = -6,
        failedToCreateATempDirectory = -7,
        failedToCopyFileFromTempDirectoryToTargetDirectory = -8,
        failedToRemoveOldFile = -9,
        failedToRemoveOldLexFileInTempDir = -10,
        failedToCopyLexFileToTempDir = -11
    };
protected:
    QTemporaryDir tempDir;
    QFile hkscsFile;
    static const QString sysLexPathBefore2004;
    static const QString sysChtCJExtFilePathBefore2004;
    static const QString sysChtCJFilePathBefore2004;
    static const QString sysChtCJSpdFilePathBefore2004;
    QString batchFilePath;
    QString sysChtCJExtFileAclPathBefore2004;
    QString sysChtCJFileAclPathBefore2004;
    QString sysChtCJSpdFileAclPathBefore2004;
    std::set<std::string> hkscsSet;
    std::map<std::string, std::vector<std::shared_ptr<MSCJKanji>>> mscjKanjiMap;
    int loadLex(QString targetFilePath);
    int loadTable(QString targetFilePath);
    int removeLexFileInSystemPath();
    int installLexFileToSystemPath(bool isRestore);
    int changeRegistrySettings();
    int encodePlainTextToMSCJCodeChart();
    int clearTemporaryData();
    int saveFile();
    int m_lineCount;
    unsigned m_counter;
    QFileInfo lexFileOutputPath;
    std::ofstream lexFileOutput;

signals:
    void setProgressBar(int lower, int upper);
    void setProgressBarValue(int value);
    void addProgressBarValue();
    void problemOccuredAtLine(int lineNo);
public slots:
    int lexInstaller(QString targetFilePath);
    int baker(QString targetFilePath);
};


#endif // MSCJTABLE_H



#include "MSCJTable.h"

const QString MSCJTable::sysLexPathBefore2004 = QProcessEnvironment::systemEnvironment().value("windir") + "\\InputMethod\\CHT\\";
const QString MSCJTable::sysChtCJExtFilePathBefore2004 = MSCJTable::sysLexPathBefore2004 + "ChtChangjieExt.lex";
const QString MSCJTable::sysChtCJFilePathBefore2004 = MSCJTable::sysLexPathBefore2004 + "ChtChangjie.lex";
const QString MSCJTable::sysChtCJSpdFilePathBefore2004 = MSCJTable::sysLexPathBefore2004 + "ChtChangjie.spd";

MSCJTable::MSCJTable(QObject *parent) : QObject(parent)
{
    m_lineCount = 0;
    m_counter = 0;
}

int MSCJTable::lexInstaller(QString targetFilePath) {
    std::cout << "lex複製姬啓動…" << std::endl;
    int exitCode;
    if ((exitCode = loadLex(targetFilePath))) {
        clearTemporaryData();
        return exitCode;
    }
    /*
    if ((exitCode = removeLexFileInSystemPath())) {
        return exitCode;
    }
    */
    if ((exitCode = installLexFileToSystemPath(false))) {
        clearTemporaryData();
        return exitCode;
    }
    if ((exitCode = changeRegistrySettings())) {
        clearTemporaryData();
        return exitCode;
    }
    clearTemporaryData();
    std::cout << "安裝完成。" << std::endl;
    return MSCJTable::ExitCode::installSuccess;
}

int MSCJTable::loadLex(QString targetFilePath) {
    int exitCode;
    if ((exitCode = clearTemporaryData())) {
        return exitCode;
    }
    if (!tempDir.isValid()) {
        std::cerr << "創建臨時文件夾失敗。" << std::endl;
        return MSCJTable::ExitCode::failedToCreateATempDirectory;
    }
    batchFilePath = tempDir.path() + QDir::separator() + "CopyChtCjToSystem.bat";
    sysChtCJExtFileAclPathBefore2004 = tempDir.path() + QDir::separator() + "sysChtCJExtFileAcl.dat";
    qDebug() << tempDir.path();
    QString folderPath = QApplication::applicationDirPath() + QDir::separator ();
    qDebug() << folderPath;
    if (QFile::exists(targetFilePath)) {
        qDebug() << "Lexicon file exists. ";
        QString tempLexPath = tempDir.path() + QDir::separator() + "ChtChangjieExt.lex";
        if (QFile::exists(tempLexPath)) {
            bool isremoveSuccessed = QFile::remove(tempLexPath);
            if (!isremoveSuccessed) {
                std::cerr << "未能移除臨時文件夾中的舊Lex文件" << std::endl;
                return MSCJTable::ExitCode::failedToRemoveOldLexFileInTempDir;
            }
        }
        bool isCopySuccessed;
        isCopySuccessed = QFile::copy(targetFilePath, tempLexPath);
        if (!isCopySuccessed) {
            std::cerr << "未能將Lex文件複製到臨時文件夾中" << std::endl;
            return MSCJTable::ExitCode::failedToCopyLexFileToTempDir;
        }
    }
    return MSCJTable::ExitCode::success;
}

int MSCJTable::removeLexFileInSystemPath() {
    // 這裏寫實現，移除系統文件夾中的舊lex文件。
    return MSCJTable::ExitCode::success;
}

int MSCJTable::installLexFileToSystemPath(bool isRestore) {
    // 這裏寫實現，安裝lex文件到系統文件夾。
    QFile batchFile(batchFilePath);
    if (batchFile.open(QFile::WriteOnly | QFile::Text)) {
        qDebug() << "打開了bat文件準備寫入";
        QTextStream batchFileStream(&batchFile);
        auto enc = QStringConverter::encodingForName("System");
        if (enc.has_value()) {
            batchFileStream.setEncoding(enc.value());
        } else {
            batchFileStream.setEncoding(QStringConverter::Utf8);
        };
        batchFileStream << QString("@echo off\n");
        batchFileStream << QString("\n");
        batchFileStream << QString("takeown /f \"%1\"").arg(sysChtCJExtFilePathBefore2004);

    }
    return MSCJTable::ExitCode::success;
}

int MSCJTable::changeRegistrySettings() {
    // 這裏寫實現，修改注册表。
    return MSCJTable::ExitCode::success;
}

int MSCJTable::baker(QString targetFilePath) {
    std::cout << "lex烤製姬啓動…" << std::endl;
    int exitCode;
    if ((exitCode = loadTable(targetFilePath))) {
        clearTemporaryData();
        return exitCode;
    }
    if ((exitCode = encodePlainTextToMSCJCodeChart())) {
        clearTemporaryData();
        return exitCode;
    }
    clearTemporaryData();
    if ((exitCode = saveFile())) {
        clearTemporaryData();
        return exitCode;
    }
    std::cout << "烤製完成。" << std::endl;
    return MSCJTable::ExitCode::success;
}

int MSCJTable::loadTable(QString targetFilePath) {
    int exitCode;
    if ((exitCode = clearTemporaryData())) {
        return exitCode;
    }
    qDebug() << tempDir.path();
    QString folderPath = QApplication::applicationDirPath() + QDir::separator ();
    qDebug() << folderPath;
    hkscsFile.setFileName(":/qtres/hkscs.txt");
    if (!hkscsFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        std::cerr << "沒有找到HKSCS文件" << std::endl;
        return MSCJTable::ExitCode::hkscsFileNotFound;
    }
    QTextStream hkscsFileStream(&hkscsFile);
    hkscsFileStream.setEncoding(QStringConverter::Utf8);


    QFile codeChartFile(targetFilePath);
    if (!codeChartFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        std::cerr << "沒有找到碼表文件" << std::endl;
        return MSCJTable::ExitCode::codeChartNotFound;
    }
    QTextStream codeChartFileStream(&codeChartFile);
    codeChartFileStream.setEncoding(QStringConverter::Utf8);

    if (!tempDir.isValid()) {
        std::cerr << "創建臨時文件夾失敗。" << std::endl;
        return MSCJTable::ExitCode::failedToCreateATempDirectory;
    }
    lexFileOutputPath.setFile(targetFilePath);          // 獲取txt碼表路径，讓生成的lex放在同一個目錄下。
    lexFileOutput = std::ofstream((tempDir.path() + QDir::separator() + "ChtChangjieExt.lex").toUtf8(), std::ios::out | std::ios::binary);

    emit setProgressBar(0, 0);

    while (!hkscsFileStream.atEnd()) {
        hkscsSet.insert(std::string(hkscsFileStream.readLine().toUtf8()));
    }

    while (!codeChartFileStream.atEnd()) {
        ++m_counter;
        QString qCodeChartFileReadline = codeChartFileStream.readLine();
        QStringList splitTempList = qCodeChartFileReadline.split(QRegularExpression("[\\t ]+"));
        if (splitTempList.length() != 2) {
            std::cerr << "碼表格式可能有誤" << std::endl;
            return MSCJTable::ExitCode::codeChartFormatError;
        }
        if (splitTempList[1].count() > 2) {
            std::cerr << "不要往碼表裏塞詞組啊喂" << std::endl;
            emit problemOccuredAtLine(m_counter);
            return MSCJTable::ExitCode::thereArePhrasesInTheCodeChart;
        }
        if (splitTempList[1].toUcs4().length() > 1) {
            std::cerr << "不要往碼表裏塞詞組啊喂" << std::endl;
            emit problemOccuredAtLine(m_counter);
            return MSCJTable::ExitCode::thereArePhrasesInTheCodeChart;
        }
        if (splitTempList[0].count() > 5) {
            std::cerr << "為什麼你的倉頡有六碼，，，" << std::endl;
            emit problemOccuredAtLine(m_counter);
            return MSCJTable::ExitCode::cjCodeLengthError;
        }
        for (auto ch:splitTempList[0]) {
            if ((ch < 'a') | (ch > 'z')) {
                std::cerr << "你的編碼超出了a-z的範圍，微軟倉頡不支持。" << std::endl;
                emit problemOccuredAtLine(m_counter);
                return MSCJTable::ExitCode::cjCodeError;
            }
        }
        std::string kanji(splitTempList[1].toUtf8());
        std::string cjCode(splitTempList[0].toUtf8());
        if (mscjKanjiMap.find(cjCode) == mscjKanjiMap.end()) {
            std::shared_ptr<MSCJKanji> kanjiPtr(new MSCJKanji(cjCode, kanji, hkscsSet));
            std::vector<std::shared_ptr<MSCJKanji>> kanjiPtrVector = {kanjiPtr};
            mscjKanjiMap.insert(std::map<std::string, std::vector<std::shared_ptr<MSCJKanji>>>::value_type (cjCode, kanjiPtrVector));
        } else {
            std::shared_ptr<MSCJKanji> kanjiPtr(new MSCJKanji(cjCode, kanji, hkscsSet));
            mscjKanjiMap[cjCode].push_back(kanjiPtr);
        }
    }
    return MSCJTable::ExitCode::success;
}

int MSCJTable::encodePlainTextToMSCJCodeChart() {
    for (auto mscjKanjiMapIterator = mscjKanjiMap.begin(); mscjKanjiMapIterator != mscjKanjiMap.end(); ++mscjKanjiMapIterator) {
        std::vector<std::shared_ptr<MSCJKanji>> mscjVector = mscjKanjiMapIterator -> second;
        if (mscjVector.size() > 2) {
            if ((mscjVector[0] -> isBMPButNotCJKExtA()) && (mscjVector[1] -> isBMPButNotCJKExtA()) && (mscjVector[2]) -> isBMPButNotCJKExtA()) {
                KanjiBlockValueStrategy::kanjiBlockValueStrategyWithFirstThreeDuplicateCjCodeKanji(mscjVector);
            } else if ((mscjVector[0] -> isBMPButNotCJKExtA()) && (mscjVector[1] -> isBMPButNotCJKExtA()) && (mscjVector[1] -> kanjiFromUTF8ToOrd() <= mscjVector[0] -> kanjiFromUTF8ToOrd())) {
                KanjiBlockValueStrategy::kanjiBlockValueStrategyWithFirstTwoDuplicateCjCodeKanji(mscjVector);
            }
        } else if (mscjVector.size() == 2) {
            if ((mscjVector[0] -> isBMPButNotCJKExtA()) && (mscjVector[1] -> isBMPButNotCJKExtA()) && (mscjVector[1] -> kanjiFromUTF8ToOrd() <= mscjVector[0] -> kanjiFromUTF8ToOrd())) {
                KanjiBlockValueStrategy::kanjiBlockValueStrategyWithFirstTwoDuplicateCjCodeKanji(mscjVector);
            }
        }
        ++this->m_lineCount;
    }

    emit setProgressBar(0, this->m_lineCount);
    emit setProgressBarValue(0);

    std::vector<unsigned char> bytesInTotal;
    std::vector<unsigned char> bytesOfHead;
    std::vector<unsigned char> bytesOfNeck;
    std::vector<unsigned char> bytesOfBody;
    unsigned int neckOffSet = 0x00;
    for (auto mscjKanjiMapIterator = mscjKanjiMap.begin(); mscjKanjiMapIterator != mscjKanjiMap.end(); ++mscjKanjiMapIterator) {
        for (auto mscjVectorIterator = mscjKanjiMapIterator -> second.begin(); mscjVectorIterator != mscjKanjiMapIterator -> second.end(); ++ mscjVectorIterator) {
            std::vector<unsigned char> tempVec = EncodeInt::encodeInt32(neckOffSet);
            bytesOfNeck.insert(bytesOfNeck.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));
            tempVec = (*mscjVectorIterator) -> encodeToMSCJBodyData();
            neckOffSet += (*mscjVectorIterator) -> encodeOffset();
            bytesOfBody.insert(bytesOfBody.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));
            tempVec = std::vector<unsigned char>{0x00, 0x00};
            bytesOfBody.insert(bytesOfBody.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));
        }
        emit addProgressBarValue();
    }

    emit setProgressBar(0, 0);
    emit setProgressBarValue(0);

    std::vector<unsigned char> tempVec = {0x6D, 0x73, 0x63, 0x6A, 0x78, 0x75, 0x64, 0x70};
    bytesOfHead.insert(bytesOfHead.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));

    tempVec = EncodeInt::encodeInt32(0x01);
    bytesOfHead.insert(bytesOfHead.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));

    tempVec = EncodeInt::encodeInt32(0x40);
    bytesOfHead.insert(bytesOfHead.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));

    tempVec = EncodeInt::encodeInt32(unsigned(64 + bytesOfNeck.size()));
    bytesOfHead.insert(bytesOfHead.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));

    tempVec = EncodeInt::encodeInt32(unsigned(64 + bytesOfNeck.size() + bytesOfBody.size()));
    bytesOfHead.insert(bytesOfHead.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));

    tempVec = EncodeInt::encodeInt32(m_counter);
    bytesOfHead.insert(bytesOfHead.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));

    tempVec = EncodeInt::encodeInt32(0x00);
    bytesOfHead.insert(bytesOfHead.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));

    tempVec = EncodeInt::encodeInt32(0x559234d3);   // Meaning is unknown yet, place a special value here.
    bytesOfHead.insert(bytesOfHead.end(), std::make_move_iterator(tempVec.begin()), std::make_move_iterator(tempVec.end()));

    tempVec = EncodeInt::encodeInt32(0x00);
    for (int i = 0; i < 7; ++i) {
        bytesOfHead.insert(bytesOfHead.end(), tempVec.begin(), tempVec.end());
    }
    std::vector<unsigned char>().swap(tempVec);

    bytesInTotal.insert(bytesInTotal.end(), bytesOfHead.begin(), bytesOfHead.end());
    bytesInTotal.insert(bytesInTotal.end(), bytesOfNeck.begin(), bytesOfNeck.end());
    bytesInTotal.insert(bytesInTotal.end(), bytesOfBody.begin(), bytesOfBody.end());

    lexFileOutput.write((const char*)&bytesInTotal[0], bytesInTotal.size());
    lexFileOutput.close();
    return MSCJTable::ExitCode::success;
}

int MSCJTable::clearTemporaryData() {
    if (hkscsFile.isOpen()) {
        hkscsFile.close();
    }
    if (mscjKanjiMap.size()) {
        for (auto mscjKanjiMapIterator = mscjKanjiMap.begin(); mscjKanjiMapIterator != mscjKanjiMap.end(); ++mscjKanjiMapIterator) {
            for (auto mscjVectorIterator = mscjKanjiMapIterator -> second.begin(); mscjVectorIterator != mscjKanjiMapIterator -> second.end(); ++ mscjVectorIterator){
                mscjVectorIterator->reset();
            }
        }
        mscjKanjiMap.clear();
    }
    if (hkscsSet.size()) {
        hkscsSet.clear();
    }
    m_lineCount = 0;
    m_counter = 0;
    return MSCJTable::ExitCode::success;
}

int MSCJTable::saveFile() {
    if (QFile::exists(lexFileOutputPath.path() + QDir::separator() + "ChtChangjieExt.lex")) {
        bool isremoveSuccessed = QFile::remove(lexFileOutputPath.path() + QDir::separator() + "ChtChangjieExt.lex");
        if (!isremoveSuccessed) {
            std::cerr << "未能移除舊文件" << std::endl;
            return MSCJTable::ExitCode::failedToRemoveOldFile;
        }
    }
    bool isCopySuccessed;
    isCopySuccessed = QFile::copy((tempDir.path() + QDir::separator() + "ChtChangjieExt.lex"), (lexFileOutputPath.path() + QDir::separator() + "ChtChangjieExt.lex"));
    if (!isCopySuccessed) {
        std::cerr << "文件拷貝失敗" << std::endl;
        return MSCJTable::ExitCode::failedToCopyFileFromTempDirectoryToTargetDirectory;
    }
    emit setProgressBar(0, 1);
    return MSCJTable::ExitCode::success;

}


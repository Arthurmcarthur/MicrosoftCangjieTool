#include "mscjtoolwidget.h"
#include "ui_mscjtoolwidget.h"

MSCJToolWidget::MSCJToolWidget(QWidget *parent)
    : QWidget(parent)
    , ui(new Ui::MSCJToolWidget)
{
    ui->setupUi(this);
    this->resize(582, 240);
    #if defined(Q_OS_WIN32)
    setWindowIcon(QIcon(":/qtres/cjico.ico"));
    #endif
    startButton = new QPushButton("烤製碼表", this);
    mscjTable = new MSCJTable();
    mscjTable->setParent(this);
    connect(startButton, &QPushButton::clicked, this, &MSCJToolWidget::encodeWithFileName);

    firstLineNoWithProblem = 0;
    connect(mscjTable, &MSCJTable::problemOccuredAtLine, this, &MSCJToolWidget::setFirstLineNoWithProblem);

    fileLabel = new QLabel("碼表:", this);

    fileButton = new QPushButton("瀏覽", this);
    // fileButton->move(400, 200);
    connect(fileButton, &QPushButton::clicked, this, &MSCJToolWidget::fileButtonPressed);
    connect(this, &MSCJToolWidget::disableButtons, startButton, &QPushButton::setDisabled);
    connect(this, &MSCJToolWidget::disableButtons, fileButton, &QPushButton::setDisabled);


    codeChartFilePathLineEdit = new CodeChartFilePathLine("", this);

    progressBar = new QProgressBar(this);

    connect(this, &MSCJToolWidget::disableButtons, codeChartFilePathLineEdit, &QLineEdit::setDisabled);
    connect(mscjTable, &MSCJTable::setProgressBar, progressBar, &QProgressBar::setRange);
    connect(mscjTable, &MSCJTable::setProgressBarValue, progressBar, &QProgressBar::setValue);
    connect(mscjTable, &MSCJTable::addProgressBarValue, this, &MSCJToolWidget::addProgressBarValue);

    authorLabel = new QLabel("作者:", this);
    authorInfo = new QLineEdit("一位不願透露姓名的倉頡低手@骨折輸入法", this);
    authorInfo->setDisabled(true);

    installButton = new QPushButton("安裝碼表", this);
    connect(this, &MSCJToolWidget::disableButtons, installButton, &QPushButton::setDisabled);
    #if defined(Q_OS_WIN32)
    connect(installButton, &QPushButton::clicked, this, &MSCJToolWidget::installCodeChart);
    #else
    connect(installButton, &QPushButton::clicked, this, &MSCJToolWidget::systemNotSupportedToInstallCodeChart);
    #endif

    srcLabel = new QLabel("源代碼:", this);
    srcPage = new QLineEdit("https://github.com/Arthurmcarthur/MicrosoftCangjieTool", this);
    srcPage->setDisabled(true);


    layout = new QGridLayout();

    layout->addWidget(fileLabel, 0, 0, 1, 1);
    layout->addWidget(codeChartFilePathLineEdit, 0, 1, 1, 11);
    layout->addWidget(fileButton, 0, 12, 1, 1);
    layout->addWidget(installButton, 1, 6, 1, 1);
    layout->addWidget(startButton, 1, 7, 1, 1);
    layout->addWidget(authorLabel, 2, 0, 1, 1);
    layout->addWidget(authorInfo, 2, 1, 1, 11);
    layout->addWidget(srcLabel, 3, 0, 1, 1);
    layout->addWidget(srcPage, 3, 1, 1, 11);
    layout->addWidget(progressBar, 4, 1, 1, 11);

    vecteurPourUneFille = std::unique_ptr<std::vector<unsigned char>>(new std::vector<unsigned char> {
        0xE8, 0xB0, 0xA8, 0xE4, 0xBB, 0xA5, 0xE6, 0x9C, 0xAC, 0xE7, 0xA8, 0x8B, 0xE5, 0xBA, 0x8F,
        0xE7, 0x8C, 0xAE, 0xE7, 0xBB, 0x99, 0xE6, 0xAE, 0xB5, 0xE9, 0x94, 0xA6, 0xE5, 0x9F, 0x8E
    });

    this->setLayout(layout);

}

void MSCJToolWidget::fileButtonPressed() {
    disableButtons(true);
    codeChartFilePathLineEdit->setText(QFileDialog::getOpenFileName(this,"瀏覽文件","./","碼表文件(*.txt *.lex)"));
    //打印要打开的文件名
    if (codeChartFilePathLineEdit->text() == "") {
        QMessageBox::information(this,"提示", "請選擇一個UTF-8 without BOM文本編碼的碼表文件，左邊為倉頡編碼，右邊為漢字，一行一字，中間以製表符或半角空格分隔。例如：\na\t日\na\t曰\naa\t昌\n您也可以選中現成的lex文件安裝到Windows 10系統中。");
    }
    disableButtons(false);
}

void MSCJToolWidget::encodeWithFileName() {
    disableButtons(true);
    QRegExp lexRegex("^.+\\.lex$", Qt::CaseInsensitive);
    QRegExpValidator lexRegexValidator(lexRegex, 0);
    QRegExp txtRegex("^.+\\.txt$", Qt::CaseInsensitive);
    QRegExpValidator txtRegexValidator(txtRegex, 0);
    int pos = 0;
    QString targetStr = codeChartFilePathLineEdit->text();
    if (lexRegexValidator.validate(targetStr, pos) == QValidator::Acceptable) {
        QMessageBox::information(this,"提示", "您似乎選中了一個烤製完畢的lex文件。對於該文件，您可以選擇：\n- 直接安裝該碼表（需要Windows 10）。");
        disableButtons(false);
        return;
    }
    if (txtRegexValidator.validate(targetStr, pos) != QValidator::Acceptable) {
        QMessageBox::information(this,"提示", "您似乎沒有選中合乎要求的碼表文件。本程序支持將選中txt文件轉換為lex碼表並保存，或將lex碼表安裝到您的電腦上（後者需要Windows 10）");
        disableButtons(false);
        return;
    }
    QFuture<int> future = QtConcurrent::run(mscjTable, &MSCJTable::baker, codeChartFilePathLineEdit->text());
    while (!future.isFinished()) {
        QApplication::processEvents(QEventLoop::AllEvents, 100);
    }
    disableButtons(false);
    mscjTableExitCodeHandler(future.result());

}

void MSCJToolWidget::addProgressBarValue() {
    this->progressBar->setValue(this->progressBar->value() + 1);
}

void MSCJToolWidget::installCodeChart() {
    QMessageBox::information(this,"(♯｀∧´)", "尚未實現的功能。");
    qDebug() << "尚未實現的功能。";
}

void MSCJToolWidget::systemNotSupportedToInstallCodeChart() {
    QMessageBox::information(this,"(♯｀∧´)", "Windows 10才能使用該功能。");
    qDebug() << "Windows 10才能使用該功能。";
}

//void MSCJToolWidget::changeOpenFileText() {
//    openFile = codeChartFilePathLineEdit->text();
//}

void MSCJToolWidget::setFirstLineNoWithProblem(int lineNo) {
    firstLineNoWithProblem = lineNo;
}

void MSCJToolWidget::mscjTableExitCodeHandler(int result) {
    switch (result) {

    case MSCJTable::ExitCode::installSuccess:
        QMessageBox::information(this,"\(≧▽≦)/", "碼表安裝完成。");
        break;

    case MSCJTable::ExitCode::success:
        QMessageBox::information(this,"\(≧▽≦)/", "烤製完成。生成的lex碼表文件和你的txt文件放到了同一個目錄，請查閱。");
        break;

    case MSCJTable::ExitCode::hkscsFileNotFound:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "沒有找到HKSCS文件。");
        break;

    case MSCJTable::ExitCode::codeChartNotFound:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "沒有找到碼表文件。");
        break;

    case MSCJTable::ExitCode::codeChartFormatError:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "碼表格式有誤。請確保碼表是無BOM的UTF8文本編碼，並且左碼右字，中間以Tab或半角空格分隔。");
        break;

    case MSCJTable::ExitCode::thereArePhrasesInTheCodeChart:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "請不要往碼表裏塞詞組，因為微軟倉頡不支持。請檢查第" + QString::number(firstLineNoWithProblem) + "行。");
        this->setFirstLineNoWithProblem(0);
        break;

    case MSCJTable::ExitCode::cjCodeLengthError:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "倉頡編碼超過了五碼。該問題首次出現於第" + QString::number(firstLineNoWithProblem) + "行。");
        this->setFirstLineNoWithProblem(0);
        break;

    case MSCJTable::ExitCode::cjCodeError:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "倉頡編碼超出了a-z的範圍。該問題首次出現於第" + QString::number(firstLineNoWithProblem) + "行。");
        this->setFirstLineNoWithProblem(0);
        break;

    case MSCJTable::ExitCode::failedToCreateATempDirectory:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "創建臨時文件夾失敗，我也不知道為什麼。");
        break;

    case MSCJTable::ExitCode::failedToCopyFileFromTempDirectoryToTargetDirectory:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "未能從臨時文件夾中將文件複製到與您指定的txt的相同文件夾中。這可能是因為權限不足，或是文件被佔用等等原因。");
        break;

    case MSCJTable::ExitCode::failedToRemoveOldFile:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "在您指定的txt的相同文件夾檢測到同名lex。程序未能將其移除，這可能是因為權限不足。");
        break;

    case MSCJTable::ExitCode::failedToRemoveOldLexFileInTempDir:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "未能移除臨時文件夾中的舊lex文件。");
        break;

    case MSCJTable::ExitCode::failedToCopyLexFileToTempDir:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "未能成功將lex文件拷貝到臨時文件夾。");
        break;

    default:
        this->progressBar->setValue(0);
        this->progressBar->setRange(0, 1);
        QMessageBox::information(this,"(♯｀∧´)", "申必錯誤，請檢查你的姿势。");
        break;
    }

}

MSCJToolWidget::~MSCJToolWidget()
{
    delete ui;
}


/*
 * I've got a hole, oh in my pocket
 * where all the money has gone
 * I've got a whole lot of work to do with your heart
 * Cause it's so busy, mine's not
 */













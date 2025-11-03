#ifndef MSCJTOOLWIDGET_H
#define MSCJTOOLWIDGET_H

#include <QWidget>
#include <QPushButton>
#include "MSCJTable.h"
#include "CodeChartFilePathLine.h"
#include <QFileDialog>
#include <QMessageBox>
#include <QLineEdit>
#include <QProgressBar>
#include <QGridLayout>
#include <QLabel>
#include <QRegularExpressionValidator>
#include <QRegularExpression>


QT_BEGIN_NAMESPACE
namespace Ui { class MSCJToolWidget; }
QT_END_NAMESPACE

class MSCJToolWidget : public QWidget
{
    Q_OBJECT

public:
    MSCJToolWidget(QWidget *parent = nullptr);
    ~MSCJToolWidget();
    void mscjTableExitCodeHandler(int result);
signals:
    void disableButtons(bool);

public slots:
    void fileButtonPressed();
    void encodeWithFileName();
    void installCodeChart();
    void systemNotSupportedToInstallCodeChart();
    void addProgressBarValue();

private:
    Ui::MSCJToolWidget *ui;
    QPushButton* startButton;
    QLabel* fileLabel;
    QPushButton* fileButton;
    MSCJTable* mscjTable;
    CodeChartFilePathLine* codeChartFilePathLineEdit;
    QProgressBar* progressBar;
    QGridLayout* layout;
    QLabel* authorLabel;
    QLineEdit* authorInfo;
    QPushButton* installButton;
    QLabel* srcLabel;
    QLineEdit* srcPage;
    int firstLineNoWithProblem;
    std::unique_ptr<std::vector<unsigned char>> vecteurPourUneFille;
    void changeOpenFileText();
    void setFirstLineNoWithProblem(int lineNo);
};
#endif // MSCJTOOLWIDGET_H

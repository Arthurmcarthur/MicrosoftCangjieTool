#include "CodeChartFilePathLine.h"

CodeChartFilePathLine::CodeChartFilePathLine(QWidget* parent):
    QLineEdit(parent)
{
    this->setAcceptDrops(true);

}

CodeChartFilePathLine::CodeChartFilePathLine(const QString& targetFilePathStr, QWidget* parent):
    QLineEdit(targetFilePathStr, parent)
{
    this->setAcceptDrops(true);
}

void CodeChartFilePathLine::dragEnterEvent(QDragEnterEvent* event) {
    event->acceptProposedAction();
}

void CodeChartFilePathLine::dropEvent(QDropEvent* event) {
    QString name = event->mimeData()->urls().first().toLocalFile();
    this->setText(name);
}

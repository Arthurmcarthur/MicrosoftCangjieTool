#ifndef CODECHARTFILEPATHLINE_H
#define CODECHARTFILEPATHLINE_H

#include <QLineEdit>
#include <QDragEnterEvent>
#include <QDropEvent>
#include <QMimeData>

class CodeChartFilePathLine : public QLineEdit
{
    Q_OBJECT
public:
    explicit CodeChartFilePathLine(QWidget *parent = nullptr);
    explicit CodeChartFilePathLine(const QString& targetFilePathStr, QWidget *parent = nullptr);
    void dragEnterEvent(QDragEnterEvent *) override;
    void dropEvent(QDropEvent *) override;
};

#endif // CODECHARTFILEPATHLINE_H

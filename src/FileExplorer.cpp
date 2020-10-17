#include "FileExplorer.h"
#include "ui_FileExplorer.h"

FileExplorer::FileExplorer(QWidget *parent) :
    QMainWindow(parent),
    ui(new Ui::FileExplorer)
{
    ui->setupUi(this);
    this->setAttribute(Qt::WA_DeleteOnClose,true);
    QString openFile="";
    QString saveFile="";
    //文件对话框获取要打开的文件名
    openFile=QFileDialog::getOpenFileName(this,"打开","./","文本文件(*.txt *.ini)");
    //打印要打开的文件名
    if (openFile != "") {
        QMessageBox::information(this,"open",openFile);
    }
    qDebug() << "关闭";
    this->close();

}


FileExplorer::~FileExplorer()
{
    delete ui;
}

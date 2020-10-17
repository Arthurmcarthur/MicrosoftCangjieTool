#include "mscjtoolwidget.h"

#include <QApplication>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    MSCJToolWidget w;
    w.setWindowTitle("微軟倉頡碼表編輯器");
    w.show();
    return a.exec();
}

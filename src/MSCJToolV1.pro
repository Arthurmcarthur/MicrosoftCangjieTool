QT += core gui widgets core5compat
QT       += core gui
QT       += concurrent

greaterThan(QT_MAJOR_VERSION, 4): QT += widgets

CONFIG += c++11

# The following define makes your compiler emit warnings if you use
# any Qt feature that has been marked deprecated (the exact warnings
# depend on your compiler). Please consult the documentation of the
# deprecated API in order to know how to port your code away from it.
DEFINES += QT_DEPRECATED_WARNINGS

TARGET = MSCJTool

# You can also make your code fail to compile if it uses deprecated APIs.
# In order to do so, uncomment the following line.
# You can also select to disable deprecated APIs only up to a certain version of Qt.
#DEFINES += QT_DISABLE_DEPRECATED_BEFORE=0x060000    # disables all the APIs deprecated before Qt 6.0.0

SOURCES += \
    CodeChartFilePathLine.cpp \
    EncodeInt.cpp \
    KanjiBlockValueStrategy.cpp \
    MSCJKanji.cpp \
    MSCJTable.cpp \
    main.cpp \
    mscjtoolwidget.cpp

HEADERS += \
    CodeChartFilePathLine.h \
    EncodeInt.hpp \
    KanjiBlockValueStrategy.hpp \
    MSCJKanji.hpp \
    MSCJTable.h \
    mscjtoolwidget.h

FORMS += \
    FileExplorer.ui \
    mscjtoolwidget.ui

# Default rules for deployment.
qnx: target.path = /tmp/$${TARGET}/bin
else: unix:!android: target.path = /opt/$${TARGET}/bin
!isEmpty(target.path): INSTALLS += target

RESOURCES += \
    res.qrc

RC_ICONS = cjico.ico
ICON = cjico.icns

QMAKE_APPLE_DEVICE_ARCHS = arm64 x86_64

//
//  MSCJKanji.cpp
//  mscjencodecpp
//
//  Created by Qwetional on 19/6/2020.
//  Copyright © 2020 Qwetional. All rights reserved.
//

#include "MSCJKanji.hpp"

MSCJKanji::MSCJKanji(std::string cjCode, std::string kanjiValue, std::set<std::string>& hkscsSet) {
    m_cjCode = cjCode;
    m_kanjiValue = kanjiValue;
    if (this -> isBMP()) {
        if (this -> isCJKExtA()) {
            m_kanjiBlock = MSCJKanji::MSCJCharacterset::extA;
        } else {
            m_kanjiBlock = MSCJKanji::MSCJCharacterset::hkscsBMP;
        }
    } else {
        if (hkscsSet.find(kanjiValue) != hkscsSet.end()) {
            m_kanjiBlock = MSCJKanji::MSCJCharacterset::hkscsNonBMP;
        } else {
            m_kanjiBlock = MSCJKanji::MSCJCharacterset::nonBMP;
        }
    }
}

std::string MSCJKanji::getCjCode() {
    return m_cjCode;
}

void MSCJKanji::setCjCode(std::string cjCode) {
    m_cjCode = cjCode;
}

std::string MSCJKanji::getKanjiValue() {
    return m_kanjiValue;
}

void MSCJKanji::setKanjiValue(std::string kanjiValue) {
    m_kanjiValue = kanjiValue;
}

enum MSCJKanji::MSCJCharacterset MSCJKanji::getKanjiBlock() {
    return m_kanjiBlock;
}
void MSCJKanji::setKanjiBlock(enum MSCJKanji::MSCJCharacterset kanjiBlock) {
    m_kanjiBlock = kanjiBlock;
}

unsigned MSCJKanji::kanjiFromUTF8ToOrd() {
    unsigned unicodeVal;
    const unsigned char* charPtr = (const unsigned char*)m_kanjiValue.c_str();
    int charNum;

    if ((charPtr[0] & 0xF8) == 0xF0) {
        unicodeVal = (charPtr[0] & 0x07) << 18;
        charNum = 4;
    }
    else if ((charPtr[0] & 0xF0) == 0xE0) {
        unicodeVal = (charPtr[0] & 0x0F) << 12;
        charNum = 3;
    }
    else if ((charPtr[0] & 0xE0) == 0xC0) {
        unicodeVal = (charPtr[0] & 0x1F) << 6;
        charNum = 2;
    }
    else {
        unicodeVal = charPtr[0] & 0x7F;
        charNum = 1;
    }

    for (int counter = 1; counter < charNum; ++counter) {
        int offset = (charNum - counter - 1) * 6;
        unicodeVal |= ((charPtr[counter] & 0x3F) << offset); // 使用 |= 比較安全
    }
    return unicodeVal;
}


bool MSCJKanji::isBMP() {
    unsigned ord = this -> kanjiFromUTF8ToOrd();
    if (ord <= 0xFFFF) {
        return true;
    } else {
        return false;
    }
}

bool MSCJKanji::isCJKExtA() {
    unsigned ord = this -> kanjiFromUTF8ToOrd();
    if ((0x3400 <= ord) && (ord <= 0x4DB5)) {
        return true;
    } else {
        return false;
    }
}

bool MSCJKanji::isBMPButNotCJKExtA() {
    if ((this -> isBMP()) && !(this -> isCJKExtA())) {
        return true;
    } else {
        return false;
    }
}

unsigned MSCJKanji::encodeOffset() {
    unsigned offSet = unsigned(0x10 + 2 * m_cjCode.length());
    if (this -> isBMP()) {
        offSet -= 0x02;
    }
    return offSet;
}

std::vector<unsigned char> MSCJKanji::kanjiFromUTF8ToUTF16LE() {
    unsigned ord = this -> kanjiFromUTF8ToOrd();
    std::vector<unsigned char> charVector;
    if (ord <= 0xFFFF) {
        charVector.push_back(ord & 0xFF);
        charVector.push_back((ord >> 8) & 0xFF);
    } else {
        ord -= 0x10000;
        unsigned highSurrogatePairValue = 0xD800 + ((ord >> 10) & 0x3FF);
        unsigned lowSurrogatePairValue = 0xDC00 + (ord & 0x3FF);
        charVector.push_back(highSurrogatePairValue & 0xFF);
        charVector.push_back((highSurrogatePairValue >> 8) & 0xFF);
        charVector.push_back(lowSurrogatePairValue & 0xFF);
        charVector.push_back((lowSurrogatePairValue >> 8) & 0xFF);
    }
    return charVector;
}

std::vector<unsigned char> MSCJKanji::cjCodeFromUTF8ToUTF16LE() {
    std::vector<unsigned char> charVector;
    for (size_t i = 0; i < m_cjCode.length(); ++i) {
        charVector.push_back((unsigned char)m_cjCode[i]);
        charVector.push_back(0x00);
    }
    return charVector;
}

std::vector<unsigned char> MSCJKanji::encodeToMSCJBodyData() {
    std::vector<unsigned char> charVector = {0x08, 0x00, 0x08, 0x00};
    short cjCodeLength = short(m_cjCode.length());
    std::vector<unsigned char> tempVector = EncodeInt::encodeInt16(cjCodeLength * 2 + 0xA);
    charVector.insert(charVector.end(), std::make_move_iterator(tempVector.begin()), std::make_move_iterator(tempVector.end()));
    tempVector = EncodeInt::encodeInt16(m_kanjiBlock);
    charVector.insert(charVector.end(), std::make_move_iterator(tempVector.begin()), std::make_move_iterator(tempVector.end()));
    tempVector = this -> cjCodeFromUTF8ToUTF16LE();
    charVector.insert(charVector.end(), std::make_move_iterator(tempVector.begin()), std::make_move_iterator(tempVector.end()));
    tempVector = {0x00, 0x00};
    charVector.insert(charVector.end(), std::make_move_iterator(tempVector.begin()), std::make_move_iterator(tempVector.end()));
    tempVector = this -> kanjiFromUTF8ToUTF16LE();
    charVector.insert(charVector.end(), std::make_move_iterator(tempVector.begin()), std::make_move_iterator(tempVector.end()));
    return charVector;
}



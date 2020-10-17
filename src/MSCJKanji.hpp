//
//  MSCJKanji.hpp
//  mscjencodecpp
//
//  Created by Qwetional on 19/6/2020.
//  Copyright © 2020 Qwetional. All rights reserved.
//

#ifndef MSCJKanji_hpp
#define MSCJKanji_hpp

#include <string>
#include <set>
#include <vector>
#include "EncodeInt.hpp"

class MSCJKanji {
public:
    enum MSCJCharacterset {
        nonBMP = 0x02,
        hkscsBMP = 0x04,
        extA = 0x05,
        hkscsNonBMP = 0x06
    };
    MSCJKanji(std::string cjCode, std::string kanjiValue, std::set<std::string>& hkscsSet);
    std::string getCjCode();
    void setCjCode(std::string cjCode);
    std::string getKanjiValue();
    void setKanjiValue(std::string kanjiValue);
    enum MSCJKanji::MSCJCharacterset getKanjiBlock();
    void setKanjiBlock(enum MSCJKanji::MSCJCharacterset kanjiBlock);
    unsigned kanjiFromUTF8ToOrd();
    bool isBMP();
    bool isCJKExtA();
    bool isBMPButNotCJKExtA();
    unsigned encodeOffset();
    std::vector<unsigned char> kanjiFromUTF8ToUTF16LE();
    std::vector<unsigned char> cjCodeFromUTF8ToUTF16LE();
    std::vector<unsigned char> encodeToMSCJBodyData();
    
    

protected:
    std::string m_cjCode;
    std::string m_kanjiValue;
    enum MSCJKanji::MSCJCharacterset m_kanjiBlock;
};

#endif /* MSCJKanji_hpp */

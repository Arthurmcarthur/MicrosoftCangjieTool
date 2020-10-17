//
//  KanjiBlockValueStrategy.cpp
//  mscjencodecpp
//
//  Created by Qwetional on 19/6/2020.
//  Copyright © 2020 Qwetional. All rights reserved.
//

#include "KanjiBlockValueStrategy.hpp"

void KanjiBlockValueStrategy::kanjiBlockValueStrategyWithFirstTwoDuplicateCjCodeKanji(std::vector<std::shared_ptr<MSCJKanji>>& targetMSCJVector) {
    targetMSCJVector[0] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::extA);
    targetMSCJVector[1] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::hkscsBMP);
}
void KanjiBlockValueStrategy::kanjiBlockValueStrategyWithFirstThreeDuplicateCjCodeKanji(std::vector<std::shared_ptr<MSCJKanji>>& targetMSCJVector) {
    int unicodeCodepointCompareList[] = {1, 1, 1};
    if (targetMSCJVector[0] -> kanjiFromUTF8ToOrd() > targetMSCJVector[1] -> kanjiFromUTF8ToOrd()) {
        unicodeCodepointCompareList[0] += 1;
    } else {
        unicodeCodepointCompareList[1] += 1;
    }
    if (targetMSCJVector[1] -> kanjiFromUTF8ToOrd() > targetMSCJVector[2] -> kanjiFromUTF8ToOrd()) {
        unicodeCodepointCompareList[1] += 1;
    } else {
        unicodeCodepointCompareList[2] += 1;
    }
    if (targetMSCJVector[0] -> kanjiFromUTF8ToOrd() > targetMSCJVector[2] -> kanjiFromUTF8ToOrd()) {
        unicodeCodepointCompareList[0] += 1;
    } else {
        unicodeCodepointCompareList[2] += 1;
    }
    
    int strategyCode = unicodeCodepointCompareList[0] * 100 + unicodeCodepointCompareList[1] * 10 + unicodeCodepointCompareList[2];
    
    switch (strategyCode) {
        case 123:
        case 132:
        case 231:
            targetMSCJVector[0] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::extA);
            targetMSCJVector[1] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::extA);
            targetMSCJVector[2] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::hkscsBMP);
            break;
        case 213:
        case 321:
        case 312:
            targetMSCJVector[0] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::extA);
            targetMSCJVector[1] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::hkscsBMP);
            targetMSCJVector[2] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::hkscsBMP);
            break;
        default:
            targetMSCJVector[0] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::hkscsBMP);
            targetMSCJVector[1] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::hkscsBMP);
            targetMSCJVector[2] -> setKanjiBlock(MSCJKanji::MSCJCharacterset::hkscsBMP);
            break;
    }
}

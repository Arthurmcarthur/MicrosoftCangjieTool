//
//  KanjiBlockValueStrategy.hpp
//  mscjencodecpp
//
//  Created by Qwetional on 19/6/2020.
//  Copyright © 2020 Qwetional. All rights reserved.
//

#ifndef KanjiBlockValueStrategy_hpp
#define KanjiBlockValueStrategy_hpp

#include <vector>
#include <memory>
#include "MSCJKanji.hpp"

class KanjiBlockValueStrategy {
public:
    static void kanjiBlockValueStrategyWithFirstTwoDuplicateCjCodeKanji(std::vector<std::shared_ptr<MSCJKanji>>& targetMSCJVector);
    static void kanjiBlockValueStrategyWithFirstThreeDuplicateCjCodeKanji(std::vector<std::shared_ptr<MSCJKanji>>& targetMSCJVector);
};

#endif /* KanjiBlockValueStrategy_hpp */

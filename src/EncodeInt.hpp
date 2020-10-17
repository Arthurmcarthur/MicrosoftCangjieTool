//
//  EncodeInt.hpp
//  mscjencodecpp
//
//  Created by Qwetional on 18/6/2020.
//  Copyright © 2020 Qwetional. All rights reserved.
//

#ifndef EncodeInt_hpp
#define EncodeInt_hpp

#include <vector>

class EncodeInt {
public:
    static std::vector<unsigned char> encodeInt16(unsigned short value);
    static std::vector<unsigned char> encodeInt32(unsigned value);
};

#endif /* EncodeInt_hpp */

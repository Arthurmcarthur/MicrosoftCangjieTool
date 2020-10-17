//
//  EncodeInt.cpp
//  mscjencodecpp
//
//  Created by Qwetional on 18/6/2020.
//  Copyright © 2020 Qwetional. All rights reserved.
//

#include "EncodeInt.hpp"

std::vector<unsigned char> EncodeInt::encodeInt16(unsigned short value) {
    std::vector<unsigned char> bytes(2);
    bytes[0] = (value & 0xFF);
    bytes[1] = ((value >> 8) & 0xFF);
    return bytes;
}

std::vector<unsigned char> EncodeInt::encodeInt32(unsigned value) {
    std::vector<unsigned char> bytes(4);
    bytes[0] = (value & 0xFF);
    bytes[1] = ((value >> 8) & 0xFF);
    bytes[2] = ((value >> 16) & 0xFF);
    bytes[3] = ((value >> 24) & 0xFF);
    return bytes;
}

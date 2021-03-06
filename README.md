# Cangjie3-Plus

使用它可以生成微軟倉頡的ChtChangjieExt.lex（2004版本后作ChtCangjieExt.lex）文件。

## 說明

微軟倉頡碼表編輯器，原為微軟倉頡碼表生成姬，以Python寫成。只是速度緩慢，後用Swift、C++重寫生成部分，考慮到跨平台等因素，最終使用C++（Qt）寫了帶GUI的本工具，跨macOS/Windows兩個平台。
該編輯器的功能和界面參考xionghuaidong以C#(.Net)寫成的[微軟五筆碼表編輯器](https://gitee.com/gitwub/WubiTools)，在原本預計應有「安裝碼表」、「生成碼表」等功能，由於本人的拖延症，「安裝碼表」功能至今未完成。: (  
雖然如此發佈有些倉促，但因為最近拖延症極度惡化+忙碌，預計今年無法完成剩下的一些代碼。再加上我已承諾過10月中旬會放出本程序，因此本編輯器的版本號暫定為0.1.1alpha，供各位試用其生成碼表功能，並在[此](https://github.com/Arthurmcarthur/MicrosoftCangjieTool)放出源碼。

本軟件使用如下格式的碼表生成lex文件：
UTF-8 without BOM文本編碼的碼表文件，左邊為倉頡編碼，右邊為漢字，一行一字，中間以製表符或半角空格分隔。如果您不確定，可以下載[這裏](https://raw.githubusercontent.com/Arthurmcarthur/MicrosoftCangjieTool/master/cj5_sample.txt)的示例碼表。

## 緣由

微軟倉頡原廠碼表錯訛甚多，影響使用，有甚者為了使用微軟倉頡，死記硬背錯碼。為了方便使用者，寫出本程序。本程序免費使用，無意侵犯任何公司或人的著作權。

## 致謝
在上方提到的[xionghuaidong](https://gitee.com/xionghuaidong)先生的程序在很多地方啓發了我，接下來要完成的碼表安裝功能，將參考他的實現。[mrhso](https://github.com/mrhso)首先以JavaScript完成了lex擴展區的讀取，在他的基礎之上，我才弄清了整個lex擴展區文件的結構。可以說，沒有他們，就不會有這個程序，在此向他們表示謝意。
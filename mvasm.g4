grammar mvasm;


program : (instr NEWLINE)* instr NEWLINE*
        ;


instr   :   LD wrt_reg COMMA val    #instrLD
        |   ST reg COMMA mem        #instrST
        |   MOV reg COMMA reg       #instrMOV
        |   ADD wrt_reg COMMA reg   #instrADD
        |   PSH reg                 #instrPSH
        |   POP reg                 #instrPOP
        |   INC wrt_reg             #instrINC
        |   DEC wrt_reg             #instrDEC
        |   JMP VARIABLE            #instrJMP
        |   JMPF number             #instrJMPF
        |   JMPB number             #instrJMPB
        |   JZ reg COMMA VARIABLE   #instrJZ
        |   JNZ reg COMMA VARIABLE  #instrJNZ
        |   SRCF                    #instrSRCF
        |   WLKT                    #instrWLKT
        |   WLKW                    #instrwlkW
        |   WLK reg                 #instrWLK
        |   EAT                     #instrEAT
        |   END                     #instrEnd
        |   NOP                     #instrNOP
        |   VARIABLE COLON          #instrLabel
        ;

val     :   mem                  #valmem
        |   OPAR number CPAR     #valnumber
        ;

mem     :   address                     #memRel
        |   OBRACE address CBRACE       #memAbs
        ;

address :   number
        |   reg
        ;

reg     :   wrt_reg | prt_reg ;


gen_reg : 'R1' | 'R2'| 'R3'| 'R4'| 'R5'| 'R6'| 'R7'| 'R8'| 'R9'
        ;

wrt_reg :   gen_reg | 'SRF'
        ;

prt_reg : 'CS' | 'CH' | 'DS' | 'PC' | 'SP' | 'PS' | 'SRR' | 'DRS' | 'NRG' | 'STM'
        ;

number  :   DIGIT+
        ;

ADD :   'ADD';
DEC :   'DEC';
EAT :   'EAT';
END :   'END';
INC :   'INC';
JMP :   'JMP';
JMPB:   'JMPB';
JMPF:   'JMPF';
JZ  :   'JZ';
JNZ :   'JNZ';
LD  :   'LD';
NOP :   'NOP';
MOV :   'MOV';
POP :   'POP';
PSH :   'PSH';
SRCF:   'SRCF';
ST  :   'ST';
WLK :   'WLK';
WLKT:   'WLKT';
WLKW:   'WLKW';

COMMA   :   ',';
OPAR    :   '(';
CPAR    :   ')';
OBRACE  :   '{';
CBRACE  :   '}';
COLON   :   ':';
DIGIT   :   [0-9];

NEWLINE   : '\r' '\n' | '\n' | '\r';

VARIABLE    :   [a-zA-Z][a-zA-Z0-9]*
            ;
WS
   : [ \r\n] + -> skip
   ;

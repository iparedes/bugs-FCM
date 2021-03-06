import logging
from analyzer import *
import tools
import compiler

logger = tools.setup_logger('vm_logger', 'vm.log', logging.DEBUG)

from compiler import *


"""
Keep it simple
"""


MEM_SIZE=256        # Size of memory block
PROTECTED_SIZE=20   # Protected memory cannot be modified using code, just by mutation
GEN_REGS=8          # Number of general purpose registers
CODE_PCTG=0.25      # Percentage of memory extra-allocated to the Code Segment
STEPS_CYCLE=50      # Max number of steps in a run to avoid infinte loops or neverending programs


# Description of protected memory cells (only for the initial VM)
# These cells are the first positions of memory
# Offspringed VM is created from the values in the memory
PROTECTED=[
    ('ZERO',0),
    ('MEMSIZE',MEM_SIZE),
    ('PROTECTED',PROTECTED_SIZE),
    ('GENREGS',GEN_REGS),
    ('CODEPCTG',CODE_PCTG),
    ('STEPSCYCLE',STEPS_CYCLE),
    ('BRAND',1) # Brand determines friend/foe. It is used by search operations. 0 is reserved for food. >0 are bugs
]

# CS: Code Segment. Starts after the protected area
# PC: Program Counter. Points to the next instruction to execute
# DS: Data Segment
# SP: Stack Pointer
# HP: Heap Pointer
# PS: Program Start
REGS=['CS', 'DS', 'PC', 'SP', 'HP','PS']


class VM:
    def __init__(self,memsize=MEM_SIZE,mem=None,regs=None):
        """The registers, internally are representated by numbers, 0 is the first register in REGS,
        """
        self.MemSize=memsize
        self.Regs=[]
        self.ProtSymbols={} # Dictionary: Key is the protected symbol, Value is the memory absolute position
        self.RegSymbols={}  # Dictionary: Key is the register symbol, Value is the index of the registers array
        self.Memory=[0]*self.MemSize # todo: initialize to random to give more chances in mutation. This will require
                                     # todo: a redo of the load-find-blocks mechanism. Maybe using a Program Allocation Table

        self.PAT={} # Programs Allocation Table. Contains the memory addresses that the programs have been loaded in
        # Tries to accelerate access to registers
        self._pcidx=REGS.index('PC')
        self._csidx=REGS.index('CS')
        self._dsidx=REGS.index('DS')
        self._spidx=REGS.index('SP')
        self._hpidx=REGS.index('HP')
        self._psidx=REGS.index('PS')


        # Creates Protsymbols to access the memory protected data by name
        for count,elem in enumerate(PROTECTED,0):
            self.ProtSymbols[elem[0]]=count

        # Accelerates access to some memory positions
        self._brandpos=self.ProtSymbols['BRAND']

        # Start populating the registers list and dictionary of symbols
        for count,elem in enumerate(REGS,0):
            self.RegSymbols[elem]=count
        # watchout here
        self.initialize(mem,regs)

    # initializes memory and registers
    # it is used by the init function, so it takes default values,
    # or used by the generate function (by providing memory and registers
    # to generate a VM according to the memory contents (e.g. memory size could have been
    # modified by mutation, but not made effective yet
    def initialize(self, mem=None, regs=None):
        if not mem:
            # initializes from standard values
            # Populates protected memory
            for count,elem in enumerate(PROTECTED,0):
                self.Memory[count]=elem[1]
            for i in REGS:
                self.Regs.append(0)
            start=len(REGS)
            size=self.Memory[self.ProtSymbols['GENREGS']]
            for count in range(0,size):
                self.RegSymbols['R'+str(count)]=start+count
                self.Regs.append(0)
            # Set some initial values
            # The Code Segment starts right after the protected area
            prot_size=self.get_mem(self.ProtSymbols['PROTECTED'])
            self.set_reg('CS',prot_size)
            # The code segment has a size determined as percentage of the non-protected memory
            mem_size=self.get_mem(self.ProtSymbols['MEMSIZE'])
            code_pctg=self.get_mem(self.ProtSymbols['CODEPCTG'])
            code_size=int((mem_size-prot_size)*code_pctg)
            # The Data Segment starts after the code segment, (the code segment starts right after protected area
            self.set_reg('DS',prot_size+code_size)
            # Initializes the Heap Pointer to the start of the Data Segment
            self.set_reg('HP',prot_size+code_size)
            # The Stack grows from the bottom of the memory upwards
            # The SP points to the current head of the stack, so as initially there is nothing in the stack,
            # it points outside the memory (MEMSIZE)
            self.set_reg('SP',self.MemSize)
        else:
            # initializes from values in memory
            #todo: should do some checking on boundaries (e.g. protected growing bigger than total memory
            # Populates protected memory
            prot_size=mem[self.ProtSymbols['PROTECTED']]
            for i in range(0,prot_size):
                self.Memory[i]=mem[i]
            for i in range(0,len(REGS)):
                self.Regs.append(regs[i])
            start=len(REGS)
            size=mem[self.ProtSymbols['GENREGS']]
            for count in range(0,size):
                self.RegSymbols['R'+str(count)]=start+count
                self.Regs.append(regs[start+count])
            # Set some initial values
            # The Code Segment starts right after the protected area
            prot_size=mem[self.ProtSymbols['PROTECTED']]
            self.set_reg('CS',prot_size)
            # The code segment has a size determined as percentage of the non-protected memory
            mem_size=mem[self.ProtSymbols['MEMSIZE']]
            code_pctg=mem[self.ProtSymbols['CODEPCTG']]
            code_size=int((mem_size-prot_size)*code_pctg)
            # The Data Segment starts after the code segment, (the code segment starts right after protected area
            self.set_reg('DS',prot_size+code_size)
            # Initializes the Heap Pointer to the start of the Data Segment
            self.set_reg('HP',prot_size+code_size)
            # The Stack grows from the bottom of the memory upwards
            # The SP points to the current head of the stack, so as initially there is nothing in the stack,
            # it points outside the memory (MEMSIZE)
            self.set_reg('SP',mem_size)
        # some values to accelerate access to memory data
        self.MaxSteps=self.get_mem(self.ProtSymbols['STEPSCYCLE'])
        self.StepsLeft=self.MaxSteps    # Controls the execution cycle


    def generate(self):
        mem_size=self.get_mem(self.ProtSymbols['MEMSIZE'])
        C=VM(mem_size,self.Memory,self.Regs)
        return C

    # Returns a clone. Basically creates a new VM and then copies the contents of the registers and memory
    # doesnt take into account possible mutations to the protected memory (e.g. memsize or # of regs
    def clone(self):
        C=VM(self.MemSize)
        C.Regs=list(self.Regs)
        C.Memory=list(self.Memory)
        return C

    def set_brand(self,brand):
        self.set_mem(self._brandpos,brand)

    def get_brand(self):
        b=self.get_mem(self._brandpos)
        return b

    # Returns the absolute address of the next free cell from pos
    def search_free_from(self,pos):
        cs=self.get_reg('CS')
        ds=self.get_reg('DS')
        i=pos
        v=self.get_mem(i)
        while v!=0:
            i+=1
            if i==ds:
                i=cs
            if i==pos:
                # No free mem
                return 0
        return i

    # Returns the size of the free block that starts on pos
    def size_of_block(self,pos):
        cs=self.get_reg('CS')
        ds=self.get_reg('DS')
        i=pos
        size=0
        v=self.get_mem(i)
        if v!=0:
            return size
        else:
            while v==0 and i<(ds-1):
                i+=1
                size+=1
                v=self.get_mem(i)
            return size

    # Returns list with free memory blocks (absolute pos,size)
    def find_blocks(self):
        cs=self.get_reg('CS')
        ds=self.get_reg('DS')
        list=[]
        pos=cs
        while pos<(ds-1):
            size=self.size_of_block(pos)
            if size>0:
                list.append((pos,size))
                pos+=size
            else:
                pos+=1
        # checks if there is a turnaround block
        l=len(list)
        if l>1:
            first=list[0]
            last=list[l-1]
            end=last[0]+last[1]
            if (first[0]==cs) and (end==(ds-1)):
                list.pop()
                list.pop(l-2)
                list.append((last[0],last[1]+first[1]))
        list.sort(key=lambda tup: tup[1])
        return list

    # loads a file in an available memory position
    def load_file(self,file):
        logger.info(file)
        stream=FileStream(file)
        #stream = antlr4.InputStream("ADD R1,R2\n")
        analyzer=Analyzer(stream)
        analyzer.Walk()
        pos=self._compile(analyzer.Context['program'])
        name=file.split('.')[0]
        if pos>=0:
            self.PAT[name]=pos
        return pos

    # files is a list of filenames to load
    def load_files(self,files):
        for f in files:
            p=self.load_file(f)
            if p<0:
                logger.error("Unable to load "+f)

    # Compiles and stores a program in memory
    # Returns the start address relative to CS
    # if the program cannot be loaded returns -1
    def _compile(self, program):
        Context={}
        Context['REGISTERS']=self.RegSymbols
        C=Compiler(program, Context)
        length_prog=len(C.bytecode)
        blocks=self.find_blocks()
        for b in blocks:
            if b[1]>=length_prog:
                pos=b[0]
                # Loads the program in an absolute address...
                self.set_mem_blk(pos,C.bytecode)
                # ...but returns the address relative to CS
                cs=self.get_reg('CS')
                pos-=cs
                return pos
        return -1

    # Sets to start the execution of code at pos
    # pos can be a memory address relative to CS
    # the name of a program in the PAT
    def run(self,pos):
        if isinstance(pos,str):
            try:
                addr=self.PAT[pos]
            except:
                addr=0
        else:
            addr=pos
        self.set_reg('PS',addr)
        self.set_reg('PC',addr)
        self.StepsLeft=self.MaxSteps

    # Executes n steps of code at pos
    def cycle(self,pos,nsteps):
        self.set_reg('PC',pos)
        run=1
        while nsteps and run:
            run=self.step()
            nsteps-=1

    # Runs the next instruction
    # Returns 0 in case:
    #   the instruction is END.
    #   it has executed more than STEPSCYCLE
    # Returns 1 otherwise
    def step(self):
        if self.StepsLeft==0:
            self.StepsLeft=self.MaxSteps
            return 0
        self.StepsLeft-=1
        op_code=self._get_pc_code()
        #symb_op_code=OP_CODES[op_code]
        symb_op_code=compiler.get_symbol_op_code(op_code)
        logger.info(symb_op_code)
        logger.debug(self.show_architecture())
        try:
            func=getattr(self,symb_op_code)
            func()
            if symb_op_code=='_end':
                return 0
            else:
                return 1
        except BaseException as e:
            text="Error: "+str(e)+"\n"
            text+="OpCode: "+str(op_code)+"\n"
            text+=self.show_architecture()+"\n"+self.show_memory()
            logger.error(text)
            return 0


    def get_reg(self,idx):
        # Look at this!!
        # Expects access to the regs by index mostly, but if gets the symbolic name catches the exception and acts
        try:
            return self.Regs[idx]
        except TypeError:
            id=self.RegSymbols[idx]
            return self.Regs[id]

    def set_reg(self,idx,val):
        try:
            self.Regs[idx]=val
        except  TypeError:
            idx=self.RegSymbols[idx]
            self.Regs[idx]=val
        except BaseException as e:
            text="Error: "+str(e)+"\n"
            text+="Idx: "+str(idx)+" Val: "+str(val)+"\n"
            text+=self.show_architecture()+"\n"+self.show_memory()
            logger.error(text)

    def set_mem(self,addr,val):
        if addr<0 or addr>=self.MemSize:
            addr=addr%self.MemSize
        if addr>=self.get_reg('CS'):
            self.Memory[addr]=val

    def get_mem(self,addr):
        if addr<0 or addr>=self.MemSize:
            addr=addr%self.MemSize
        return self.Memory[addr]

    def set_mem_blk(self,addr,blk):
        cont=addr
        while blk:
            item=blk.pop(0)
            self.set_mem(cont,item)
            cont+=1

    # gets the value of the address pointed by the PC
    # PC is relative to CS
    def _get_pc_code(self):
        cs=self.get_reg(self._csidx)

        pcabs=self.get_reg(self._pcidx)+cs

        data=self.get_mem(pcabs)
        pcabs+=1

        ds=self.get_reg(self._dsidx)
        # Checks if the pc overrouns the code segment
        if pcabs==ds:
            pcabs=cs

        self.set_reg(self._pcidx,pcabs-cs)
        return data

    # Sets the PC as dir relative to CS
    def _set_pc(self,dir):
        cs=self.get_reg(self._csidx)
        ds=self.get_reg(self._dsidx)
        size=ds-cs

        # checks for turnarounds
        if dir>=size:
            dir=dir-size
        elif dir<0:
            dir=dir+size
        self.set_reg(self._pcidx,dir)


    def _push(self,val):
        logger.info(val)
        # SP points to the current head, so first we make it grow
        sp=self.get_reg(self._spidx)
        hp=self.get_reg(self._hpidx)
        ds=self.get_reg(self._dsidx)
        # The stack grows upwards
        sp-=1

        if sp==ds+hp:
            # the stack has reached the heap, so roll over
            sp=self.MemSize-1

        self.set_mem(sp,val)
        self.set_reg('SP',sp)

    def _pop(self):
        sp=self.get_reg(self._spidx)
        val=self.get_mem(sp)
        logger.info(val)
        sp+=1
        if sp==self.MemSize:
            # the stack goes beyond the bottom of the memory (maybe too many pops), it rolls over to the beginning
            # of the stack segment (delimited by the end of the heap)
            hp=self.get_reg(self._hpidx)
            sp=hp
        self.set_reg('SP',sp)
        return val


    def show_architecture(self):
        a="Memory size:"+str(self.MemSize)+" "
        a+="Protected size:"+str(self.get_mem(self.ProtSymbols['PROTECTED']))+" "

        for r in self.RegSymbols.keys():
            a+=r+': '+str(self.get_reg(r))+' '
        return a

    def show_memory(self,start=0,end=0):
        if end==0:
            end=len(self.Memory)
        a=""
        for i in range(start,end):
            if i%8==0:
                t='\n'+str(i)+': '
                a+=t.rjust(7)
            a+=str(self.get_mem(i)).ljust(4)+' '
        return a

    def show_memory_old(self,start=0,end=MEM_SIZE):
        for i in range(start,end):
            if i%8==0:
                t='\n'+str(i)+': '
                print(t.rjust(7),end='')
            print(str(self.get_mem(i)).ljust(4),end=' ')


    # ld1 reg addr
    # loads in reg the value in addr relative to DS
    def _ld1(self):
        reg=self._get_pc_code()
        addr=self._get_pc_code()
        # Address is relative to DS
        addr+=self.get_reg('DS')
        val=self.get_mem(addr)
        self.set_reg(reg,val)

    # ld2 reg1 reg2
    # loads in reg1 the value of the addr relative to DS stored in reg2
    def _ld2(self):
        reg1=self._get_pc_code()
        reg2=self._get_pc_code()
        addr=self.get_reg(reg2)
        # Address is relative to DS
        addr+=self.get_reg('DS')
        val=self.get_mem(addr)
        self.set_reg(reg1,val)

    # ld3 reg {addr}
    # Loads in a register the content of an absolute memory address
    def _ld3(self):
        # When it gets here, the PC points to the target register
        reg=self._get_pc_code()
        addr=self._get_pc_code()
        val=self.get_mem(addr)
        self.set_reg(reg,val)

    # ld4 reg1 {reg2}
    # Loads in reg1 the content of the absolute memory address contained in reg2
    def _ld4(self):
        reg1=self._get_pc_code()
        reg2=self._get_pc_code()
        addr=self.get_reg(reg2)
        val=self.get_mem(addr)
        self.set_reg(reg1,val)

    # Loads in reg1 a numeric value
    def _ld5(self):
        reg1=self._get_pc_code()
        val=self._get_pc_code()
        self.set_reg(reg1,val)


    # st1 reg addr
    # stores in addr (relative to DS) the value in reg
    def _st1(self):
        reg=self._get_pc_code()
        val=self.get_reg(reg)
        addr=self._get_pc_code()
        # Address is relative to DS
        addr+=self.get_reg('DS')
        self.set_mem(addr,val)

    # st2 reg1 reg2
    # stores in the address in reg2 (relative to DS) the value of reg1
    def _st2(self):
        reg1=self._get_pc_code()
        val=self.get_reg(reg1)

        reg2=self._get_pc_code()
        addr=self.get_reg(reg2)
        # Address is relative to DS
        addr+=self.get_reg('DS')
        self.set_mem(addr,val)

    # st3 reg {addr}
    # Stores in absolute addr the content of register reg
    def _st3(self):
        reg=self._get_pc_code()
        addr=self._get_pc_code()
        val=self.get_reg(reg)
        self.set_mem(addr,val)


    # st4 reg1 {reg2}
    # stores in the address contained in reg2 (absoloute) the value of register reg1
    def _st4(self):
        reg1=self._get_pc_code()
        reg2=self._get_pc_code()
        addr=self.get_reg(reg2)
        val=self.get_reg(reg1)
        self.set_mem(addr,val)

    def _add(self):
        reg1=self._get_pc_code()
        reg2=self._get_pc_code()
        v1=self.get_reg(reg1)
        v2=self.get_reg(reg2)
        self.set_reg(reg1,v1+v2)

    def _inc(self):
        reg=self._get_pc_code()
        v=self.get_reg(reg1)
        v+=1
        self.set_reg(reg,v)

    def _dec(self):
        reg=self._get_pc_code()
        v=self.get_reg(reg)
        v-=1
        self.set_reg(reg,v)


    # mov reg1 reg2
    # copies content of reg2 to reg1
    def _mov(self):
        reg1=self._get_pc_code()
        reg2=self._get_pc_code()
        val=self.get_reg(reg2)
        self.set_reg(reg1,val)

    # psh reg
    # pushes the content of register to the stack
    def _psh(self):
        reg=self._get_pc_code()
        val=self.get_reg(reg)
        self._push(val)

    # pop reg
    # pops the head of the stack into register
    def _pp(self):
        reg=self._get_pc_code()
        val=self._pop()
        self.set_reg(reg,val)

    # jmp dir
    # sets the PC to dir relative to the SP
    def _jmp(self):
        dir=self._get_pc_code()
        sp=self.get_reg(self._spidx)
        dir+=sp
        self.set_reg(self._pcidx,dir)

    # jmpf val
    # Jumps forward. Adds val to the PC
    def _jmpf(self):
        val=self._get_pc_code()
        pc=self.get_reg(self._pcidx)
        self._set_pc(pc+val)

    # jmpb val
    # Jumps backward. Substracts val from the PC
    def _jmpb(self):
        val=self._get_pc_code()
        pc=self.get_reg(self._pcidx)
        self._set_pc(pc-val)

    # Jumps if reg is zero
    # address is relative to SP
    def _jz(self):
        reg=self._get_pc_code()
        val=self.get_reg(reg)
        if val==0:
            dir=self._get_pc_code()
            sp=self.get_reg(self._spidx)
            dir+=sp
            self._set_pc(dir)

    # Jumps if reg is not zero
    # address is relative to SP
    def _jnz(self):
        reg=self._get_pc_code()
        val=self.get_reg(reg)
        if val!=0:
            dir=self._get_pc_code()
            sp=self.get_reg(self._spidx)
            dir+=sp
            self._set_pc(dir)

    def _nop(self):
        pass

    def _end(self):
        pass


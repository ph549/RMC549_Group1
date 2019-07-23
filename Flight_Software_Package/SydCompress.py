#-------------------------------------------------------------------------------
# Name:        BityByte
# Purpose:     Does stuff with bits and bytes, useful for compression
# Author:      Syd
# Created:     13-04-2019
#-------------------------------------------------------------------------------
import math
import numpy as np
import os
import time
#import zlib

def Float2Long(flt,np=0,lng=0):
    """set lng to get back a 4-byte representation(long integer)"""
    if flt==0:
        return([0,0,0,0])
    sign=int(flt < 0) #positive or negative
    expt=math.floor(math.log2(abs(flt))) #exponent
    frac=abs(flt)/(2**expt)-1 #get it into 1+0.xxx form
    new=0
    for i in range(0,23):
        new=new<<1
        frac*=2.0
        if frac>=1.0:
            new+=1
            frac-=1.0
    if frac>.5 and frac<1:
        new+=1
    if lng:
        return((sign<<31)+((expt+127)<<23)+(new))
    fir=((sign<<7)|((expt+127)>>1)) #shift sign to first pos, then write exponent
    sec=(((1-expt%2)<<7)|(new>>16)) #keep last bit of exp and first 7 of frac
    thr=(new%65536)>>8 #get last 16, then shift right 8
    frt=new%256 #get the last 8 bits
    if np:
        return(np.array([fir,sec,thr,frt]))
    else:
        return([fir,sec,thr,frt])


def Long2Float(lng):
    if type(lng) in (list,np.ndarray):
        lng=(lng[0]<<24)+(lng[1]<<16)+(lng[2]<<8)+(lng[3])
    sign=(-1)**(lng>>31)
#    print(bin(lng))
    expt=((lng>>23) & 0b011111111)
    if expt==255:
        if (lng%(1<<23))==0:
            if sign==1:
                return(np.Inf)
            else:
                return(np.NINF)
        else:
            return(np.nan)
    #do calc in 1 line for best precision?
    elif expt==0:
        return(sign*(2**(expt-126))*((lng%(1<<23))/(1<<23)))
    else:
        return(sign*(2**(expt-127))*((1+(lng%(1<<23))/(1<<23))))


def Force2Int(num):
    if type(num)==float:
        return(Float2Long(num,lng=1))
    elif type(num)==int:
        return(num)
    else:
        return(0)


def Int2Bin(num,size=None,bitwise=0):
    try: #safety
        len(num)
    except TypeError:
        num=[num]
    except Excepttion as e:
        print(e)
        return(0)

    if size is None:
        size=np.log2(num) #smallest possible size
    if not bitwise:
        size=np.ceil(np.array(size)/8).astype(np.uint)*8 #size in bytes

    ret=np.zeros(np.sum(size),dtype=np.bool)
    offset=0
    for i in range(len(num)):
        n=num[i] #grab a number
        for j in range(size[i]-1,-1,-1):
            ret[offset+j]=n%2 #get the least bit
            n//=2 #shift the bits of the number
        offset+=size[i] #move to next spot in output
    return(np.packbits(ret[0:offset])) #convert bits to bytes


def Bin2Int(data,size=[8],sign=[1]):
    bits=np.unpackbits(data)
    offset=0
    ret=[0]*len(size)
    for elem in range(len(size)):
        offset+=size[elem]
        exps=np.arange(size[elem])
        raised=bits[offset-exps-1]*np.power(2,exps)
        ret[elem]=np.sum(raised)
        if sign[elem]==-1 and ret[elem]>2**(size[elem]-1):
            ret[elem]=ret[elem]-2**size[elem] #signs
    return(ret)


class SydCompress(object): #use an object mainly to load crushForm and keep it loaded
    def __init__(self,hard=0):
        #dcf=os.path.dirname(__file__)+"\\RMC549_Group1\\Flight_Software_Package\\DataCrush.txt"
        dcf="/home/pi/RMC549Repos/RMC549_Group1/Flight_Software_Package/DataCrush.txt"
        with open(dcf) as f:
            form=eval(f.read()) #loads my dictionary
            ln=len(form)
            self.name=[""]*ln
            self.mult=[1]*ln
            self.digt=[0]*ln
            self.bits=[16]*ln
            self.clip=[0]*ln
            for i in range(ln):
                try:
                    self.name[i]=form[i][0]
                    self.mult[i]=form[i][1]
                    self.digt[i]=10**form[i][2]
                    self.bits[i]=form[i][3]
                    self.clip[i]=form[i][4]
                except IndexError:
                    pass
            print("loaded crushForm")
        self.hard=hard #try to go bitwise for compression

    def Break(self,message):
        out=[] #a bunch of integers
        parts=message.split(",")
        out.append(BreakPiTime(parts[0]))
        for i in range(len(parts)):
            if self.mult[i] is not 0 and self.bits[i] is not 0:
                try:          
                    num=float(parts[i])*abs(self.mult[i])
                    if self.digt[i]>1:
                        num=num%self.digt[i]
                    clip=round(num)
                    out.append(int(clip))
                except Exception as err:
                    out.append(2**self.bits[i]-1)
                    print(self.name[i]," had error: ",err)
        szs=[y for y in self.bits if y != 0]
        byt=Int2Bin(out,szs,bitwise=self.hard)
        return(byt.tobytes())

    def Rebuild(self,data:bytes):
        out=[]
        szs=[]
        tmul=[]
        sent=[]
        for i in range(len(self.name)):
            if self.bits[i]!=0:
                szs.append(self.bits[i])
                tmul.append(self.mult[i])
                sent.append(i)
        dats=Bin2Int(np.frombuffer(data,dtype=np.uint8),szs,sign=np.sign(tmul))
        for i in range(len(tmul)):
            rediv=dats[i]/max(abs(tmul[i]),1)
            out.append(rediv+self.clip[sent[i]])
        out[0]=FixPiTime(out[0])
        return(out)


def BreakPiTime(timeStamp):
    #timestamp=20190717_08:32:39.021639
    h,m,s=timeStamp[9:].split(":")
    return((int(h)*3600+int(m)*60+round(float(s))))

def FixPiTime(timeAmount):
    hr=timeAmount//3600
    mt=(timeAmount//60)%60
    sc=timeAmount%60
    ts="{:02.0f}:{:02.0f}:{:02.0f}".format(hr,mt,sc)
    return(time.strftime("%Y%m%d_")+ts)


if __name__ == '__main__':
    breaker=SydCompress(hard=1)
    msg="20190717_08:32:39.021639,43068,155920.00,5207.88309,N,10637.94724,W,04,00500,M,-0.11,-0.15,9.95,0.00,-0.19,0.00,20.06,3.25,-48.00,0.00,-0.75,1.00,0.00,0.00,0.11,-0.12,-0.17,9.80,27,0,3,0,0,907,0,16608,81,10,58,8,81,10,25.70"
    print(msg.split(","))
    these=breaker.Break(msg)
    recon=breaker.Rebuild(these)
    print(recon)
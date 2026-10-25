"""Synthetic GU bytes through frozen SiLU/H32/A8 into exact Host Down."""
import unittest
from unittest import mock

import numpy as np

from host import scalellm_mlp_gu_only as down
from host.scalellm_mlp_linear import MLPLinearFormatError
from model.mlp_fixed import hadamard32_product_normalized,minmax_a8_quantize_s35


class GuToHostDownTests(unittest.TestCase):
    def test_GU_byte_payload_frozen_preprocess_then_fullK_Host_Down(self):
        payload=bytearray(1376256)
        for row in range(16):
            offset=row*16*3
            payload[offset:offset+3]=(16<<16).to_bytes(3,'little',signed=True)
            payload[768+offset:768+offset+3]=(2<<16).to_bytes(3,'little',signed=True)
        # SiLU(+16) bypass timesUp(+2) is exactly+32/F16. Only lane0 of group0
        # is nonzero; original independent integer helpers supply H32/MinMax.
        h=hadamard32_product_normalized([32<<16]+[0]*31)
        quant=minmax_a8_quantize_s35(h.values)
        q_expected=np.zeros((16,14336),np.uint8);q_expected[:,:32]=quant.values
        m_expected=np.zeros((16,448),np.uint32);m_expected[:,0]=quant.metadata
        q,m=down.prepare_down_arrays(payload)
        np.testing.assert_array_equal(q,q_expected);np.testing.assert_array_equal(m,m_expected)
        g=np.arange(448)[:,None,None];c=np.arange(48)[None,:,None];k=np.arange(32)[None,None,:]
        w=((g*7+c*3+k*11)%16-8).astype(np.int8)
        codes=np.ones((448,48),np.uint8);shifts=np.full((448,48),12,np.uint8)
        weights=down.DownWeights(w,codes,shifts)
        actual=down.prepare_and_run_down(payload,weights,require_production_shape=False)
        # Independent direct group0-only expectation; all other447 contribute0.
        expected=np.empty((16,48),np.int64)
        for row in range(16):
            for col in range(48):
                dot=sum((int(q_expected[row,lane])-quant.zero_point)*int(w[0,col,lane]) for lane in range(32))
                raw=dot*quant.scale_code
                shift=quant.scale_shift+12
                acc=raw<<(24-shift) if shift<=24 else raw>>(shift-24)
                rounded=(abs(acc)+128)//256
                expected[row,col]=max(-2147483648,min(2147483647,-rounded if acc<0 else rounded))
        np.testing.assert_array_equal(actual,expected)

    def test_unrepresentable_S35_stops_before_Down_matmul(self):
        # AllGate/Up=S24_MAX produces a product/H32 range beyond format05Dmax.
        encoded=(8388607).to_bytes(3,'little',signed=True)
        payload=encoded*(1376256//3)
        weights=down.DownWeights(np.ones((448,16,32),np.int8),np.ones((448,16),np.uint8),np.full((448,16),6,np.uint8))
        with mock.patch.object(down,'down_blocked_int64') as kernel:
            with self.assertRaises(MLPLinearFormatError):down.prepare_and_run_down(payload,weights)
            kernel.assert_not_called()


if __name__=='__main__':unittest.main()

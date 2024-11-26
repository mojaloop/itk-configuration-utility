##########################################################################
#  (C) Copyright Mojaloop Foundation. 2024 - All rights reserved.        #
#                                                                        #
#  This file is made available under the terms of the license agreement  #
#  specified in the corresponding source code repository.                #
#                                                                        #
#  ORIGINAL AUTHOR:                                                      #
#       James Bush - jbush@mojaloop.io                                   #
#                                                                        #
#  CONTRIBUTORS:                                                         #
#       James Bush - jbush@mojaloop.io                                   #
##########################################################################

import unittest

from pkitools import PkiTools


class TestPkiTools(unittest.Testcase):
    def test_init(self):
        pkiTools = PkiTools()



if __name__ == '__main__':
    unittest.main()

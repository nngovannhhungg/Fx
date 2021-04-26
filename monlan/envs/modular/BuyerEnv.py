
import numpy as np
import matplotlib.pyplot as plt
from copy import deepcopy
from datetime import datetime
from dateutil import parser
from monlan.agents.RiskManager import RiskManager
import time

class BuyerEnv():
    class BuyerActionSpace():
        def __init__(self):
            self.actionsDict = { 0: "hold", 1: "buy" }
            self.n = 2
            pass

    def __init__(self, historyPrice, openerFeatureGen, buyerFeatureGen, sellerFeatureGen, startDeposit = 300,
                 lotSize=0.1, lotCoef=100000, spread = 18, spreadCoef = 0.00001, stopType = "const", takeType = "const",
                 stoplossPuncts=100, takeprofitPuncts=500, stopPos = 0, takePos = 0, maxLoss = 40000, maxTake = 40000,
                 riskPoints=110, riskLevels=5, renderFlag=True, renderDir=None, renderName=None ):
        self.historyPrice = historyPrice.copy()
        self.historyPrice.set_index("datetime", drop=True, inplace=True)
        self.historyIter = None
        self.done = False
        self.startDeposit = startDeposit
        self.deposit = self.startDeposit
        self.lotSize = lotSize
        self.lotCoef = lotCoef
        self.spread = spread
        self.spreadCoef = spreadCoef
        self.renderFlag = renderFlag
        self.renderDir = renderDir
        self.renderName = renderName
        self.stopType = stopType
        self.takeType = takeType
        self.stoplossPuncts = stoplossPuncts
        self.takeprofitPuncts = takeprofitPuncts
        self.stopPos = stopPos
        self.takePos = takePos
        self.maxLoss = maxLoss
        self.maxTake = maxTake

        self.openData = []
        self.closeData = []
        self.xData = []
        self.iStep = 0

        self.actorNames = ["buyer"]
        self.featureGenerators = {"buyer": buyerFeatureGen}
        self.action_space = {"buyer": self.BuyerActionSpace()}
        self.observation_space = {"buyer": buyerFeatureGen.featureShape}
        self.openPoint = None
        self.mode = None
        self.sumLoss = 0

        pass

    def reset(self):
        self.setMode("buyer")
        self.openPoint = None
        self.sumLoss = 0
        self.done = False
        self.deposit = self.startDeposit
        self.openData = []
        self.closeData = []
        self.xData = []
        self.iStep = 0
        if self.renderFlag == True:
            plt.close()

        self.historyIter = self.historyPrice.iterrows()
        startDate = self.getStartDate()
        self.holdIter = self.historyPrice.iterrows()
        holdDate = next(self.holdIter)
        while holdDate[0] != startDate:
            holdDate = next( self.holdIter, None )
        holdDate = next(self.holdIter, None)[0]

        obs = self.featureGenerators[self.mode].getFeatByDatetime(startDate, self.historyPrice)

        return obs

    def getStartDate(self):
        minDates = []
        for actorName in self.actorNames:
            minDates.append(self.featureGenerators[actorName].getMinDate(self.historyPrice))
        for i in range(len(minDates)):
            minDates[i] = parser.parse(str(minDates[i])).timetuple()
            minDates[i] = time.mktime( minDates[i] )
        maxDateInd = np.argmax(minDates)
        minDate = self.featureGenerators[self.actorNames[maxDateInd]].getMinDate(self.historyPrice)
        startDate = next(self.historyIter)[0]
        while startDate != minDate:
            startDate = next(self.historyIter)[0]
        return startDate

    def step(self, action):
        info = {}
        reward = None
        action = self.action_space[self.mode].actionsDict[action]
        self.iStep += 1

        nextHistoryRow = next(self.historyIter, None)
        nextHoldRow = next(self.holdIter, None)
        if nextHistoryRow is None or nextHoldRow is None:
            self.done = True
            reward = 0
            selectedList = []
            for feat in self.featureGenerators[self.mode].featureList:
                selectedList.append(0.0)
            obs = np.array(selectedList)
            if self.renderFlag == True:
                if self.renderDir is None and self.renderName is None:
                    plt.savefig("./test_plot.png", dpi=2000)
                else:
                    plt.savefig("{}{}.png".format(self.renderDir, self.renderName), dpi=2000)
            ################################################################
            #rewardDict = {}
            #rewardDict[0] = 0
            #rewardDict[1] = 0
            #if self.mode in ["buyer", "seller"] and action in ["buy", "sell"]:
            #    return obs, obs, reward, self.done, info
            #else:
            #    return obs, reward, self.done, info
            ##################################################################

            if self.mode in ["buyer", "seller"] and action in ["buy", "sell"]:
                return obs, obs, reward, self.done, info
            else:
                return obs, reward, self.done, info

        nextDate = nextHistoryRow[0]
        if self.mode == "opener":
            if action == "buy":
                if self.renderFlag == True:
                    self.render(self.iStep, nextHistoryRow[1]["open"], nextHistoryRow[1]["close"], action)
                self.openPoint = deepcopy(nextHistoryRow)
                self.sumLoss = 0
                reward = 0
                if self.stopType == "adaptive" or self.takeType == "adaptive":
                    limitsDict = self.riskManager.getAdaptiveLimits(nextDate, self.historyPrice, self.openPoint[1]["open"])
                    self.stoplossPuncts = limitsDict["stop"]
                    self.takeprofitPuncts = limitsDict["take"]
                    if self.stoplossPuncts > self.maxLoss:
                        self.stoplossPuncts = self.maxLoss
                    if self.takeprofitPuncts > self.maxTake:
                        self.takeprofitPuncts = self.maxTake
                self.mode = "buyer"
            elif action == "sell":
                if self.renderFlag == True:
                    self.render(self.iStep, nextHistoryRow[1]["open"], nextHistoryRow[1]["close"], action)
                self.openPoint = deepcopy(nextHistoryRow)
                self.sumLoss = 0
                reward = 0
                if self.stopType == "adaptive" or self.takeType == "adaptive":
                    limitsDict = self.riskManager.getAdaptiveLimits(nextDate, self.historyPrice, self.openPoint[1]["open"])
                    self.stoplossPuncts = limitsDict["stop"]
                    self.takeprofitPuncts = limitsDict["take"]
                    if self.stoplossPuncts > self.maxLoss:
                        self.stoplossPuncts = self.maxLoss
                    if self.takeprofitPuncts > self.maxTake:
                        self.takeprofitPuncts = self.maxTake
                self.mode = "seller"
            elif action == "hold":
                #self.sumLoss += -abs((nextHoldRow[1]["open"] - (nextHistoryRow[1]["open"] + 0.5 * nextHistoryRow[1]["open"])) * self.lotCoef * self.lotSize)
                #self.sumLoss += -abs((nextHistoryRow[1]["close"] - (nextHistoryRow[1]["open"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize) * 0.8
                #self.sumLoss += -np.pi * np.sqrt(self.spread) * self.spreadCoef
                self.sumLoss += -np.pi * self.spreadCoef / 2.0
                reward = self.sumLoss

            obs = self.featureGenerators[self.mode].getFeatByDatetime(nextDate, self.historyPrice)
            if self.renderFlag == True:
                self.render(self.iStep, nextHistoryRow[1]["open"], nextHistoryRow[1]["close"], action)
            return obs, reward, self.done, info

        if self.mode in ["buyer", "seller"]:
            if action == "hold":
                obs = self.featureGenerators[self.mode].getFeatByDatetime(nextDate, self.historyPrice)
                if self.mode == "buyer":
                    reward = (nextHoldRow[1]["close"] - (self.openPoint[1]["open"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
                elif self.mode == "seller":
                    #reward = (self.openPoint[1]["open"] - (nextHoldRow[1]["close"] + 0.5 * nextHoldRow[1]["close"])) * self.lotCoef * self.lotSize
                    reward = (self.openPoint[1]["open"] - (nextHoldRow[1]["close"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
                if self.renderFlag == True:
                    self.render(self.iStep, nextHistoryRow[1]["open"], nextHistoryRow[1]["close"], action)

                ##############################
                rewardDict = {}
                if self.mode == "buyer":
                        rewardDict[0] = (nextHoldRow[1]["close"] - (self.openPoint[1]["open"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
                        rewardDict[1] = (nextHistoryRow[1]["close"] - (self.openPoint[1]["open"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
                elif self.mode == "seller":
                        rewardDict[0] = (self.openPoint[1]["open"] - (nextHoldRow[1]["close"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
                        rewardDict[1] = (self.openPoint[1]["open"] - (nextHistoryRow[1]["close"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize

                #################################
                info["takeprofit"] = self.isTriggeredTakeprofit(nextHistoryRow)
                info["stoploss"] = self.isTriggeredStoploss(nextHistoryRow)
                info["limitOrder"] = self.checkLimitTrigger(info["takeprofit"], info["stoploss"])
                if info["limitOrder"]:
                    rewardDict = self.getLimitReward(info["takeprofit"], info["stoploss"])
                    self.mode = "opener"
                    nextOpenerObs = self.featureGenerators[self.mode].getFeatByDatetime(nextDate, self.historyPrice)
                    info["nextOpenerState"] = nextOpenerObs
                    self.deposit += rewardDict[0]
                    print("Limit order triggered. Reward = {}".format(rewardDict[0]))
                return obs, rewardDict, self.done, info
                ##############################
                return obs, reward, self.done, info
            if action == "buy":
                reward = (nextHistoryRow[1]["close"] - (self.openPoint[1]["open"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
            elif action == "sell":
                reward = (self.openPoint[1]["open"] - (nextHistoryRow[1]["close"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
            if self.renderFlag == True:
                self.render(self.iStep, nextHistoryRow[1]["open"], nextHistoryRow[1]["close"], action)

            #####
            saveMode = self.mode
            #####

            nextCloserObs = self.featureGenerators[self.mode].getFeatByDatetime(nextDate, self.historyPrice)
            self.mode = "opener"
            nextOpenerObs = self.featureGenerators[self.mode].getFeatByDatetime(nextDate, self.historyPrice)

            ##############################
            rewardDict = {}
            if saveMode == "buyer":
                rewardDict[0] = (nextHoldRow[1]["close"] - (self.openPoint[1]["open"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
                rewardDict[1] = (nextHistoryRow[1]["close"] - (self.openPoint[1]["open"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
            elif saveMode == "seller":
                rewardDict[0] = (self.openPoint[1]["open"] - (nextHoldRow[1]["close"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize
                rewardDict[1] = (self.openPoint[1]["open"] - (nextHistoryRow[1]["close"] + self.spreadCoef * self.spread)) * self.lotCoef * self.lotSize

            ######################################
            info["takeprofit"] = self.isTriggeredTakeprofit(nextHistoryRow)
            info["stoploss"] = self.isTriggeredStoploss(nextHistoryRow)
            info["limitOrder"] = self.checkLimitTrigger(info["takeprofit"], info["stoploss"])
            if info["limitOrder"]:
                rewardDict = self.getLimitReward(info["takeprofit"], info["stoploss"])
                self.mode = "opener"
                info["nextOpenerState"] = nextOpenerObs
                print("Limit order triggered. Reward = {}".format(rewardDict[0]))
            ######################################

            self.deposit += rewardDict[1]

            return nextOpenerObs, nextCloserObs, rewardDict, self.done, info
            ##############################


            return nextOpenerObs, nextCloserObs, reward, self.done, info

    def render(self, iStep, open, close, action):
        self.openData.append(open)
        self.closeData.append(close)
        self.xData.append(iStep)
        # plt.scatter(iStep, open, c="black", s=1)
        # plt.scatter(iStep, close, c="blue", s=1)

        color = None
        linewidth = 0.1
        if self.mode == "opener":
            if action == "hold": color = "black"
            elif action == "buy":
                color = "green"
                linewidth = 0.1
            elif action == "sell":
                color = "red"
                linewidth = 0.1
        elif self.mode == "buyer":
            if action == "buy":
                color = "blue"
                linewidth = 0.1
            elif action == "hold": color = "cyan"
        elif self.mode == "seller":
            if action == "sell":
                color = "magenta"
                linewidth = 0.1
            elif action == "hold": color = "yellow"

        # plt.plot(self.xData, self.openData, c="black", linewidth=0.01)
        # plt.plot(self.xData, self.closeData, c="orange", linewidth=0.01)
        plt.plot([iStep, iStep], [open, close], c=color, linewidth=linewidth)
        # plt.scatter( iStep, close, c=color[action], s=1 )
        # plt.pause(0.0000000001)

        # if iStep % 800 == 0:
        #    plt.clf()

        pass

    def setMode(self, mode):
        if mode in ["opener", "buyer", "seller"]:
            self.mode = mode
        else:
            raise ValueError("Not correct mode. Use only: \"opener\", \"buyer\", \"seller\"")
        pass

    def isDone(self):
        return self.done

    def isTriggeredStoploss(self, nextHistoryRow):
        # stoploss
        info = {}
        info["stoploss"] = False
        if self.mode == "buyer":
            stoplossPrice = ((self.openPoint[1]["open"] - self.spreadCoef * (self.stoplossPuncts - self.spread))) * self.lotCoef * self.lotSize
            nextExtremum = nextHistoryRow[1]["low"] * self.lotCoef * self.lotSize
            if nextExtremum - stoplossPrice <= 0:
                info["stoploss"] = True
        elif self.mode == "seller":
            stoplossPrice = ((self.openPoint[1]["open"] + self.spreadCoef * (self.stoplossPuncts - self.spread))) * self.lotCoef * self.lotSize
            nextExtremum = nextHistoryRow[1]["high"] * self.lotCoef * self.lotSize
            if stoplossPrice - nextExtremum <= 0:
                info["stoploss"] = True
        return info["stoploss"]

    def isTriggeredTakeprofit(self, nextHistoryRow):
        # stoploss
        info = {}
        info["takeprofit"] = False
        if self.mode == "buyer":
            takeprofitPrice = ((self.openPoint[1]["open"] + self.spreadCoef * self.takeprofitPuncts)) * self.lotCoef * self.lotSize
            nextExtremum = nextHistoryRow[1]["high"] * self.lotCoef * self.lotSize
            if takeprofitPrice - nextExtremum <= 0:
                info["takeprofit"] = True
        elif self.mode == "seller":
            takeprofitPrice = ((self.openPoint[1]["open"] - self.spreadCoef * self.takeprofitPuncts)) * self.lotCoef * self.lotSize
            nextExtremum = nextHistoryRow[1]["low"] * self.lotCoef * self.lotSize
            if nextExtremum - takeprofitPrice <= 0:
                info["takeprofit"] = True
        return info["takeprofit"]

    def checkLimitTrigger(self, tpTrigger, slTrigger):

        limitTrigger = False
        if tpTrigger == True or slTrigger == True:
            limitTrigger = True

        return limitTrigger

    def getLimitReward(self, tpTrigger, slTrigger):
        tpReward = {}
        slReward = {}
        if tpTrigger:
            tpReward[0] = self.spreadCoef * self.takeprofitPuncts * self.lotCoef * self.lotSize
            tpReward[1] = self.spreadCoef * self.takeprofitPuncts * self.lotCoef * self.lotSize
        if slTrigger:
            slReward[0] = -self.spreadCoef * self.stoplossPuncts * self.lotCoef * self.lotSize
            slReward[1] = -self.spreadCoef * self.stoplossPuncts * self.lotCoef * self.lotSize
        limitReward = {}
        if tpTrigger == True and slTrigger == True:
            #No one can say what was triggered first on history.
            # That's why choose negative scenario.
            limitReward = slReward
        elif slTrigger:
            limitReward = slReward
        elif tpTrigger:
            limitReward = tpReward
        return limitReward

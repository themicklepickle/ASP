from __future__ import annotations

import sys
import inspect

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import List
    from shout_ahead.Intention import Intention
    from shout_ahead.AgentPool import AgentPool


#------------------- timeSinceLastCommunication predicates --------------------#
def timeSinceCommunication_0(timeSinceCommunication: int):
    return timeSinceCommunication == 0


def timeSinceCommunication_0_5(timeSinceCommunication: int):
    return 0 < timeSinceCommunication < 5


def timeSinceCommunication_5_10(timeSinceCommunication: int):
    return 5 < timeSinceCommunication < 10


def timeSinceCommunication_10_15(timeSinceCommunication: int):
    return 10 < timeSinceCommunication < 15


def timeSinceCommunication_15_20(timeSinceCommunication: int):
    return 15 < timeSinceCommunication < 20


def timeSinceCommunication_20_25(timeSinceCommunication: int):
    return 20 < timeSinceCommunication < 25
#---------------------------------- end ----------------------------------#


# EVALUATES VALIDITY OF A CUSTOM PREDICATE RELATIVE TO A COMMUNICATED INTENTION
def partnerAction(predicate: str, intention: Intention) -> bool:
    predicate = predicate.split("_", 1)

    return predicate[0] == intention.getTrafficLight().getName() and predicate[1] == intention.getAction()


# RETURN LIST OF PREDICATE FUNCTIONS AS DEFINED ABOVE
def getPredicateSet(agentPool: AgentPool):
    thisModule = sys.modules[__name__]  # Get reference to this module for next operation
    methodsDict = dict(inspect.getmembers(thisModule, predicate=inspect.isfunction))  # Get a dictionary with all methods (predicates) in this module
    # Remove all methods that are not predicates from dictionary
    methodsDict.pop("getPredicateSet")
    methodsDict.pop("getPredicateSetFromFile")
    methodsDict.pop("partnerAction")
    methodsDict.pop("getPartnerActionPredicates")

    # Seperate methods/predicates from rest of data in dictionary into a list
    predicateSet: List[str] = []
    for predicate in methodsDict:
        predicateSet.append(predicate)

    predicateSet = predicateSet + getPartnerActionPredicates(agentPool)

    return predicateSet


# RETURN LIST OF PREDICATE FUNCTIONS FROM AN INPUT FILE
def getPredicateSetFromFile(file: str):
    predicateSet: List[str] = []
    f = open(file, "r")  # Open desired file
    for x in f:
        if "//" in x:
            continue
        elif x.strip() == "":
            continue
        else:
            pred = x.split("\n")
            predicateSet.append(pred[0])
    f.close()

    return predicateSet


def getPartnerActionPredicates(agentPool: AgentPool):
    customPredicates: List[str] = []
    for tl in agentPool.getAssignedTrafficLights():
        for partner in tl.getCommunicationPartners():
            for action in partner.getAgentPool().getActionSet():
                pred = f"partnerAction_{partner.getName()}_{action}"
                customPredicates.append(pred)
            customPredicates.append(pred)
    return customPredicates

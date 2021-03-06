from __future__ import annotations

import numpy.random as npr
from random import randrange, randint, random, choice
import json

from predicate_sets import EVPredicateSet
from predicate_sets import EVCoopPredicateSet
from shout_ahead.Rule import Rule
from shout_ahead.Individual import Individual

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import List, Literal
    from shout_ahead.AgentPool import AgentPool
    from output_management.Database import Database


# Best runtime in seconds by the SUMO traffic light algorithm
global bestSUMORuntime
bestSUMORuntime = 1690

# How many of the top individuals to breed for new generation
global numOfIndividualsToMutate
global percentOfLastGenerationBred
global maxNumOfMutations

numOfIndividualsToMutate = 0.1667
percentOfLastGenerationBred = .3
maxNumOfMutations = 1  # maximum number of mutations to a rule

# Specifications for making Individuals and Rules
global maxRulePredicates
global maxRules
global maxIndividuals
global newGenerationPoolSize

maxRulePredicates = 3
maxRules = 10
maxRulesInNewGenerationSet = 20
maxIndividuals = 30

# How much runtime and rule weights matter when determining fitness of a simulation run
global runtimeFactor
global ruleWeightFactor

runtimeFactor = 1
ruleWeightFactor = 1

# Specifications for making RSev
global EVPredicateProbability
global EVCoopPredicateProbability
global maxEVRulePredicates
global maxEVCoopRulePredicates

EVPredicateProbability = 0.5  # The probability of choosing an EV predicate vs another one for RSev
EVCoopPredicateProbability = 0.5  # The probability of choosing an EV predicate vs another one for RSev_int
maxEVRulePredicates = 3
maxEVCoopRulePredicates = 3

# EV fitness parameters
global EVStopFitnessPenalty
global EVStopsFactor
global averageEVSpeedFactor

EVStopFitnessPenalty = -1  # Penalty applied to fitness for every EV stop
EVStopsFactor = 0.001
averageEVSpeedFactor = 10


def rFit(individual: Individual, simTime: int) -> float:
    """FITNESS FUNCTION FOR AN INDIVIDUAL AFTER ONE SIMULATION RUN/EPISODE"""
    # If Individual's simulation time is less than the best time, its fitness is the difference between those two values
    if simTime < bestSUMORuntime:
        return simTime - bestSUMORuntime
    else:
        # If Individual's simulation time is more than the best time, multiply it relative to how much worse it is
        bestIndivAggregateVehWaitTime = individual.getAgentPool().getBestIndividualAggregateVehWaitTime()
        indivAggrVehWaitTime = individual.getAggregateVehicleWaitTime()

        if indivAggrVehWaitTime == bestIndivAggregateVehWaitTime:
            return bestIndivAggregateVehWaitTime

        elif indivAggrVehWaitTime - bestIndivAggregateVehWaitTime < bestIndivAggregateVehWaitTime*.1:
            return indivAggrVehWaitTime*10

        elif indivAggrVehWaitTime - bestIndivAggregateVehWaitTime < bestIndivAggregateVehWaitTime*.2:
            return indivAggrVehWaitTime*20

        elif indivAggrVehWaitTime - bestIndivAggregateVehWaitTime < bestIndivAggregateVehWaitTime*.3:
            return indivAggrVehWaitTime*30

        else:
            return indivAggrVehWaitTime*40


def EVrFit(individual: Individual) -> float:
    """FITNESS FUNCTION FOR AN INDIVIDUAL AFTER ONE SIMULATION RUN/EPISODE FOR EV PARAMETERS"""
    fitness = 0

    fitness += averageEVSpeedFactor * individual.getAverageEVSpeed()
    fitness += EVStopsFactor * (EVStopFitnessPenalty * individual.getEVStops())

    return fitness


def createNewGeneration(agentPools: List[AgentPool],  useShoutahead: bool, ruleSetOptions: List[str], database: Database):
    """CREATES NEW GENERATION AFTER A SIMULATION RUN AND UPDATES AGENT POOLS' INDIVIDUAL SET WITH NEW GEN"""
    print("Creating a new Generation.")
    for ap in agentPools:
        individuals = ap.getIndividualsSet()
        individuals.sort(key=lambda x: x.getFitness(), reverse=False)

        lastIndex = int(len(individuals)*percentOfLastGenerationBred)
        newGeneration = individuals[0:lastIndex]
        numOfSurvivingIndividuals = len(newGeneration)

        print(f"max indivs is {maxIndividuals}, num of surviving indivs is {numOfSurvivingIndividuals}, num of indivs to mutate is {numOfIndividualsToMutate} " +
              f"and the final result is {(maxIndividuals-numOfSurvivingIndividuals)-(maxIndividuals*numOfIndividualsToMutate)}")
        # Create however many children possible to also leave room for max number of mutations
        for _ in range(int((maxIndividuals-numOfSurvivingIndividuals)-(maxIndividuals*numOfIndividualsToMutate))):
            parent1 = chooseFirstParent(newGeneration)
            parent2 = chooseSecondParent(newGeneration, parent1)
            newGeneration.append(crossover(parent1, parent2, useShoutahead, ruleSetOptions))

        # Randomly mutate a random number of the children
        for _ in range(int(numOfIndividualsToMutate*len(newGeneration))):
            individualToMutate = newGeneration[randrange(len(newGeneration))]
            # Simulate deepcopy() without using deepcopy() because it is slooooow and mutate copied Individual
            newGeneration.append(mutate(
                Individual(individualToMutate.getID(), individualToMutate.getAgentPool(), individualToMutate.getRS(), individualToMutate.getRSint()),
                useShoutahead
            ))

        ap.updateIndividualsSet(newGeneration)

        # Output new agent pool
        if database:
            agentPoolData = [i.getJSON() for i in newGeneration]
            database.updateAgentPool(ap.getID(), agentPoolData, "new")


# CREATE INDIVIDUALS WITH RANDOM RULES POPULATING THEIR RULE SETS BEFORE FIRST RUN
def initIndividuals(agentPool: AgentPool, useShoutahead: bool, ruleSetOptions: List[str]):
    localRSType, coopRSType, *_ = ruleSetOptions

    individuals: List[Individual] = []
    for i in range(maxIndividuals):
        RS: List[Rule] = []
        RSint: List[Rule] = []

        # Populate local rule set
        for _ in range(maxRules):
            RS.append(createRandomRule(agentPool, localRSType))

        # Populate cooperation rule set
        if useShoutahead:
            for _ in range(maxRules):
                RSint.append(createRandomRule(agentPool, coopRSType))

        # Add the newly created individual
        individuals.append(Individual(i + 1, agentPool, RS, RSint))

    return individuals


# CREATE A RANDOM RULE USING RANDOM PREDICATES AND AN AGENT POOL RELATED ACTION
def createRandomRule(agentPool: AgentPool, ruleType: str):
    conditions: List[str] = []  # Conditions for a rule

    # RS rule
    if ruleType == "RS":
        # Set conditions of rules as a random amount of random predicates
        for _ in range(randint(1, maxRulePredicates)):
            newPredicate = agentPool.getRandomRSPredicate()
            if checkValidCond(newPredicate, conditions):
                conditions.append(newPredicate)

    # RSint rule
    elif ruleType == "RSint":
        # Set conditions of rules as a random amount of random predicates
        for _ in range(randint(1, maxRulePredicates)):
            newPredicate = agentPool.getRandomRSintPredicate()  # different from RS because RSint predicates are unique to each AP
            if checkValidCond(newPredicate, conditions):
                conditions.append(newPredicate)
                # print("Conditions set now contains", conditions, "\n\n")

    # RSev rule
    elif ruleType == "RSev":
        # Ensure that at least one of the conditions is relating to an EV
        newPredicate = agentPool.getRandomRSevPredicate()  # Pick a new predicate from the EV predicate set
        conditions.append(newPredicate)  # No need to check the validity of the rule because this is the first rule

        # Add a lane predicate
        conditions.append(agentPool.getRandomEVLanePredicate())

        # Set conditions of rules as a random amount of random predicates
        for _ in range(randint(1, maxEVRulePredicates - 2)):
            if random() < EVPredicateProbability:
                newPredicate = agentPool.getRandomRSevPredicate()
            else:
                newPredicate = agentPool.getRandomRSPredicate()
            if checkValidCond(newPredicate, conditions):
                conditions.append(newPredicate)

    # RSev_int rule
    elif ruleType == "RSev_int":
        numCondToAdd = randint(1, maxEVCoopRulePredicates)

        # Set conditions of rules as a random amount of random predicates
        for _ in range(numCondToAdd):
            if random() < EVCoopPredicateProbability:
                newPredicate = agentPool.getRandomRSev_intPredicate()
                if newPredicate is None:
                    newPredicate = agentPool.getRandomRSintPredicate()
            else:
                newPredicate = agentPool.getRandomRSintPredicate()
            if checkValidCond(newPredicate, conditions):
                conditions.append(newPredicate)

        # Ensure that at least one of the conditions is relating to an EV
        if not EVCoopPredicateExists(conditions):
            newPredicate = agentPool.getRandomRSev_intPredicate()
            if newPredicate is not None:
                # Remove an element if the max number of rule predicates has already been reached
                if len(conditions) == maxEVCoopRulePredicates:
                    del conditions[randrange(len(conditions))]
                conditions.append(newPredicate)

    # Get index of possible action. SUMO changes phases on indexes
    action = randrange(0, len(agentPool.getActionSet()))  # Set rule action to a random action from ActionSet pertaining to Agent Pool being serviced

    rule = Rule(ruleType, conditions, action, agentPool)

    return rule


# CREATE A CHILD RULE BY BREEDING TWO PARENT RULES
def crossover(indiv1: Individual, indiv2: Individual, useShoutahead: bool, ruleSetOptions: List[str]):
    localRSType, coopRSType, *_ = ruleSetOptions

    identifier = str(indiv1.getID()) + "." + str(indiv2.getID())
    identifier = identifier[-4:]  # Memory saving line
    agentPool = indiv1.getAgentPool()

    # --- RS ----
    superRS = indiv1.getRS() + indiv2.getRS()
    superRS = removeDuplicateRules(superRS)  # Remove duplicate rules from set
    while len(superRS) < maxRulesInNewGenerationSet:
        superRS.append(createRandomRule(agentPool, localRSType))
    superRS.sort(key=lambda x: x.getWeight(), reverse=True)
    newRS = superRS[0:maxRules]

    # Ensure duplicate rules (with or without different weights) haven't been added to rule set. If they have, keep the one with the higher weight and mutate the other
    for rule in newRS:
        for r in newRS:
            if rule is not r:
                while set(rule.getConditions()) == set(r.getConditions()):
                    if rule.getWeight() < r.getWeight():
                        newRS.append(mutateRule(rule))
                        newRS.remove(rule)
                    else:
                        newRS.append(mutateRule(r))
                        newRS.remove(r)

    # Ensure that the rule sets are not identical
    while ruleSetsAreDuplicate(newRS, indiv1.getRS()) or ruleSetsAreDuplicate(newRS, indiv2.getRS()):
        newRS.sort(key=lambda x: x.getWeight(), reverse=True)
        ruleToMutate = newRS[len(newRS)-1]
        newRS.append(mutateRule(ruleToMutate))
        newRS.remove(newRS[len(newRS)-2])
    # ----------

    # --- RSint ---
    if useShoutahead:
        superRSint = indiv1.getRSint() + indiv2.getRSint()
        superRSint = removeDuplicateRules(superRSint)
        while len(superRSint) < maxRulesInNewGenerationSet:
            superRSint.append(createRandomRule(agentPool, coopRSType))
        superRSint.sort(key=lambda x: x.getWeight(), reverse=True)
        newRSint = superRSint[0:maxRules]

        # Ensure the same rule with different weights haven't been added to rule set. If they have, keep the one with the higher weight and mutate the other
        for rule in newRSint:
            for r in newRSint:
                if rule is not r:
                    while set(rule.getConditions()) == set(r.getConditions()):
                        if rule.getWeight() < r.getWeight():
                            newRSint.append(mutateRule(rule))
                            newRSint.remove(rule)
                        else:
                            newRSint.append(mutateRule(r))
                            newRSint.remove(r)

        # Ensure that the rule sets are not identical
        while ruleSetsAreDuplicate(newRSint, indiv1.getRSint()) or ruleSetsAreDuplicate(newRSint, indiv2.getRSint()):
            newRSint.sort(key=lambda x: x.getWeight(), reverse=True)
            ruleToMutate = newRSint[len(newRSint)-1]
            newRSint.append(mutateRule(ruleToMutate))
            newRSint.remove(newRSint[len(newRSint)-2])
    else:
        newRSint = []
    # ----------

    newIndividual = Individual(identifier, agentPool, newRS, newRSint)

    return newIndividual


def mutate(individual: Individual, useShoutahead: bool):
    # --- local RS ---
    chosenRule = individual.getRS()[randrange(len(individual.getRS()))]
    newRule = mutateRule(chosenRule)
    individual.getRS().append(newRule)
    individual.getRS().remove(chosenRule)

    # --- coop RS ---
    if useShoutahead:
        chosenRule = individual.getRSint()[randrange(len(individual.getRSint()))]
        newRule = mutateRule(chosenRule)
        individual.getRSint().append(newRule)
        individual.getRSint().remove(chosenRule)

    return individual


# MUTATES A RULE A RANDOM NUMBER OF TIMES (MAX MUTATIONS IS USER-DEFINED)
def mutateRule(rule: Rule):
    agentPool = rule.getAgentPool()
    conditions = rule.getConditions()

    # Remove a random number of conditions and add a random number of random conditions
    for _ in range(randint(1, maxNumOfMutations)):

        if len(conditions) == 1:
            numCondToRemove = 1
        else:
            numCondToRemove = randrange(1, len(conditions))

        for _ in range(numCondToRemove):
            conditions.remove(conditions[randrange(len(conditions))])

        # --- RS ---
        if rule.getType() == "RS":
            numCondToAdd = randint(1, maxRulePredicates - len(conditions))
            for _ in range(numCondToAdd):
                newPredicate = agentPool.getRandomRSPredicate()
                # If new random predicate is valid, append it to the conditions list
                if checkValidCond(newPredicate, conditions):
                    conditions.append(newPredicate)

        # --- RSint ---
        elif rule.getType() == "RSint":
            numCondToAdd = randint(1, maxRulePredicates - len(conditions))
            for _ in range(numCondToAdd):
                newPredicate = agentPool.getRandomRSintPredicate()
                # If new random predicate is valid, append it to the conditions list
                if checkValidCond(newPredicate, conditions):
                    conditions.append(newPredicate)

        # --- RSev ---
        elif rule.getType() == "RSev":
            numCondToAdd = randint(1, maxEVRulePredicates - len(conditions))

            for _ in range(numCondToAdd):
                if random() < EVPredicateProbability:
                    newPredicate = agentPool.getRandomRSevPredicate()
                else:
                    newPredicate = agentPool.getRandomRSPredicate()
                # If new random predicate is valid, append it to the conditions list
                if checkValidCond(newPredicate, conditions):
                    conditions.append(newPredicate)

            # Ensure that at least one of the conditions is relating to an EV
            if not EVPredicateExists(conditions):
                if len(conditions) == maxEVRulePredicates:
                    del conditions[randrange(len(conditions))]  # Remove an element if the max number of rule predicates has already been reached
                conditions.append(agentPool.getRandomRSevPredicate())

            # Ensure that a EV lane predicate exists in the rule
            if not EVLanePredicateExists(conditions):
                if len(conditions) == maxEVRulePredicates:
                    removed = False
                    # Loop through and remove the first non-EV predicate to ensure that there is always at least one EV predicate
                    for i, cond in enumerate(conditions):
                        condType = cond.split("_")[0]
                        if condType not in EVPredicateSet.getPredicateTypes():
                            del conditions[i]
                            removed = True
                            break
                    # If nothing was removed, then it means that all conditions were EV predicates, so a random one can be removed
                    if not removed:
                        conditions[randrange(len(conditions))]
                conditions.append(agentPool.getRandomEVLanePredicate())

        # --- RSev_int ---
        elif rule.getType() == "RSev_int":
            numCondToAdd = randint(1, maxEVCoopRulePredicates - len(conditions))

            for _ in range(numCondToAdd):
                if random() < EVCoopPredicateProbability:
                    newPredicate = agentPool.getRandomRSev_intPredicate()
                    if newPredicate is None:
                        newPredicate = agentPool.getRandomRSintPredicate()
                else:
                    newPredicate = agentPool.getRandomRSintPredicate()
                # If new random predicate is valid, append it to the conditions list
                if checkValidCond(newPredicate, conditions):
                    conditions.append(newPredicate)

            # Ensure that at least one of the conditions is relating to an EV
            if not EVCoopPredicateExists(conditions):
                newPredicate = agentPool.getRandomRSev_intPredicate()
                if newPredicate is not None:
                    # Remove an element if the max number of rule predicates has already been reached
                    if len(conditions) == maxEVCoopRulePredicates:
                        del conditions[randrange(len(conditions))]
                    conditions.append(newPredicate)

    rule.setConditions(conditions)  # set rule's new conditions
    rule.setAction(agentPool.getActionSet()[randrange(0, len(agentPool.getActionSet()))])
    rule.setWeight(0)
    return rule


# RETURNS A PARENT TO BE BREED BASED ON FITNESS PROPOTIONAL SELECTION
def chooseFirstParent(breedingPopulation: List[Individual]):
    totalFitness = sum([i.getNormalizedFitness() for i in breedingPopulation])  # Adjust fitnesses to benefit the smallest
    if totalFitness != 0:
        selection_probs = [i.getNormalizedFitness()/totalFitness for i in breedingPopulation]
        return breedingPopulation[npr.choice(len(breedingPopulation), p=selection_probs)]
    else:
        return choice(breedingPopulation)


# RETURNS A PARENT TO BE BREED BASED ON FITNESS PROPOTIONAL SELECTION
def chooseSecondParent(breedingPopulation: List[Individual], parent1: Individual):
    adjustedPopulation = breedingPopulation.copy()
    adjustedPopulation.remove(parent1)
    totalFitness = sum([i.getNormalizedFitness() for i in adjustedPopulation])
    if totalFitness != 0:
        selection_probs = [i.getNormalizedFitness()/totalFitness for i in adjustedPopulation]
        return adjustedPopulation[npr.choice(len(adjustedPopulation), p=selection_probs)]
    else:
        return choice(breedingPopulation)


# ENSURE UNIQUE PREDICATE TYPES IN CONDITIONS
def checkValidCond(cond: str, conditions: List[str]):
    predicateType = cond.split("_")[0]
    condPredicateTypes = []

    for x in conditions:
        type_ = x.split("_")[0]
        condPredicateTypes.append(type_)

    # If predicate type already exists in conditions, return false
    if predicateType in condPredicateTypes:
        return False
    else:
        return True


def EVPredicateExists(conditions: List[str]):
    EVPredicateTypes = EVPredicateSet.getPredicateTypes()
    for cond in conditions:
        condType = cond.split("_")[0]
        if condType in EVPredicateTypes:
            return True
    return False


def EVCoopPredicateExists(conditions: List[str]):
    EVCoopPredicateTypes = EVCoopPredicateSet.getPredicateTypes()
    for cond in conditions:
        condType = cond.split("_")[0]
        if condType in EVCoopPredicateTypes:
            return True
    return False


def EVLanePredicateExists(conditions: List[str]):
    for cond in conditions:
        condType = cond.split("_")[0]
        if condType == "leadingEVLane":
            return True
    return False


def removeDuplicateRules(ruleSet: List[Rule]):
    for rule in ruleSet:
        for otherRule in ruleSet:
            if rulesAreDuplicate(rule, otherRule):
                ruleSet.remove(otherRule)
    return ruleSet


# CHECK IF TWO RULES ARE DUPLICATES OF EACH OTHER
def rulesAreDuplicate(rule1: Rule, rule2: Rule):
    conds1 = rule1.getConditions()
    conds2 = rule2.getConditions()

    if rule1 is rule2 or (set(conds1) == set(conds2)):
        return True
    else:
        return False


# CHECK IF TWO RULE SETS ARE DUPLICATES OF EACH OTHER
def ruleSetsAreDuplicate(rs1: List[Rule], rs2: List[Rule]):
    return set(rs1) == set(rs2)


# RETURN SUM OF ALL WEIGHTS IN A RULE SET
def getSumRuleWeights(agentPools: List[AgentPool]) -> float:
    weightSum = 0

    for ap in agentPools:
        individuals = ap.getIndividualsSet()
        # For each individual, sum all their rule weights
        for i in individuals:
            ruleSet = i.getRS()
            weightSum += sum(rule.getWeight() for rule in ruleSet)

    if weightSum == 0:
        weightSum = 2.2250738585072014e-308  # Smallest number besides 0 in Python

    return weightSum

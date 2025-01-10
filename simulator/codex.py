#!/bin/python3


import os, time, json, hashlib
import random as random
from datetime import datetime
import matplotlib.pyplot as plt


def plotHistoricData(data, xLabel, yLabel, filename):
    plt.clf()
    plt.plot(data)
    plt.grid(True)
    plt.ylabel(yLabel)
    plt.xlabel(xLabel)
    plt.savefig(filename)
    print("Figure %s created." % filename)


def plotStackedBars(nbBars, data, legend, xLabel, yLabel, filename):
    plt.clf()
    for i in range(nbBars):
        if i == 0:
            plt.bar(range(len(data[0])), data[0], label=legend[i])
        else:
            plt.bar(range(len(data[i])), data[i], label=legend[i], bottom=data[i-1])
    plt.legend(loc="upper left")
    plt.grid(True)
    plt.ylabel(yLabel)
    plt.xlabel(xLabel)
    plt.savefig(filename)
    print("Figure %s created." % filename)


def plotPieChart(data, legend, filename):
    plt.clf()
    plt.pie(data, labels=legend, autopct='%1.1f%%', shadow=True, startangle=90)
    plt.savefig(filename)
    plt.axis("equal")
    print("Figure %s created." % filename)


class Config:
    def __init__(self):
        self.maxStoragePerNode = 9   # in Terabytes
        self.maxFileSize = 111028      # in Megabytes
        self.minFileSize = 1         # in Megabytes
        self.defaultECN = 128         # in number of blocks
        self.minNbNodes = 32         # in nodes
        self.simulationLength = 9    # in days
        self.meanUsage = 99          # in %


class Tracker:
    def __init__(self):
        self.storageUsed = []
        self.storageAvailable = []
        self.nbNodes = []
        self.nbFiles = []


class Block():
    def __init__(self, fileID, blockID, size):
        self.fileID = fileID
        self.blockID = blockID
        self.size = size


class Node():
    def __init__(self, ID, MaxStorageNode):
        self.storage = random.random() * MaxStorageNode * 1024 * 1024 # Storage in MBs
        self.available = self.storage
        self.ID = ID
        self.used = 0
        self.latency = random.random() * 100 # Latency score
        self.blocks = []

    def storeBlock(self, fileID, blockID, size):
        self.used = self.used + size
        self.available = self.storage - self.used
        #block = Block(fileID, blockID, size)
        #self.blocks.append(block) # Too much memory


class File:
    def __init__(self, ID, network):
        self.ID = ID #hashlib.sha256(str(ID).encode('utf-8')).hexdigest()
        self.size = random.random() * network.config.maxFileSize
        ECN = network.config.defaultECN
        if network.nbNodes < ECN or self.size < 1:
            self.ECK = int(ECN/8)
            self.ECM = int(ECN/8)
            self.ECN = int(ECN/4)
        elif network.nbNodes < ECN*2:
            self.ECK = int(ECN/4)
            self.ECM = int(ECN/4)
            self.ECN = int(ECN/2)
        else:
            self.ECK = int(ECN/2)
            self.ECM = int(ECN/2)
            self.ECN = int(ECN)

    def disperse(self, network):
        contracted = []
        full = []
        random.seed(time.time())
        for blockID in range(self.ECN):
            stored = 0
            while(not stored):
                r = random.randint(0, network.nbNodes-1)
                if (r not in contracted):
                    if (network.nodes[r].available > self.size/self.ECK):
                        contracted.append(r)
                        stored = 1
                    else:
                        if (r not in full):
                            full.append(r)
                        #print("Not enough space on %i: %f available for %f" % (r, network.nodes[r].available, self.size/self.ECK))
                else:
                    #print("Node %i already used for this file %s || contracted => %i full => %i" % (r, str(self.ID), len(contracted), len(full)))
                    if (len(contracted) + len(full) >= network.nbNodes):
                        break
        if len(contracted) == self.ECN:
            for r in contracted:
                network.nodes[r].storeBlock(self.ID, blockID, self.size/self.ECK)
                return 0
        elif len(contracted) > self.ECN:
            print("Warning %i contracted, needed %i." % (len(contracted), self.ECN))
        else:
            print("Warning %i contracted, needed %i." % (len(contracted), self.ECN))
            #print("Contract could not be fulfilled, only %i nodes with enough space, %i needed." % (len(contracted), self.ECN))
            if self.ECN == network.config.defaultECN/4: # Maximum ECN reduction reached
                network.rejectedFiles = network.rejectedFiles + 1
                return 0
            elif self.ECN > network.config.defaultECN/4: # ECN should be reduced
                return 1
            else:
                print("Warning, the ECN should have not reached this low")
                return 0

    def reduceECN(self):
        if (self.ECN == network.config.defaultECN) or (self.ECN == network.config.defaultECN/2):
            self.ECK = self.ECK/2
            self.ECM = self.ECM/2
            self.ECN = self.ECN/2

class Network():
    def __init__(self, conf):
        self.nodes = []
        self.files = []
        self.nbNodes = 0
        self.nbFiles = 0
        self.rejectedFiles = 0
        self.nbBlocks = 0
        self.storageProvided = 0
        self.storageUsed = 0
        self.storageAvailable = 0
        self.config = conf
        now = datetime.now()
        self.name = "Codex-"+now.strftime("%y-%m-%d-%H-%M-%S")

    def addNode(self):
        node = Node(self.nbNodes, self.config.maxStoragePerNode)
        self.nodes.append(node)
        self.nbNodes = self.nbNodes + 1
        self.storageProvided = self.storageProvided + node.storage
        self.storageAvailable = self.storageAvailable + node.storage

    def addFile(self):
        file = File(self.nbFiles, self)
        while (file.disperse(self)):
            file.reduceECN
        self.files.append(file)
        self.nbFiles = self.nbFiles + 1
        self.nbBlocks = self.nbBlocks + file.ECN
        self.storageUsed = self.storageUsed + ((file.size/file.ECK)*file.ECN)
        self.storageAvailable = self.storageAvailable - ((file.size/file.ECK)*file.ECN)

    def trackStats(self, sec, tracker):
        os.system("clear")
        print("|==================================================================================|")
        print("| Day  | Hour  | Nodes |  Files   | Rejected | Prov.(TBs) | Used(TBs) | Avai.(TBs) |")
        print("|==================================================================================|")
        print("| %04i | %02i:00 | %05i | %08i |  %06i  | %010.4f | %09.3f | %010.3f |" % (sec/(3600*24), (sec/3600)%24, self.nbNodes, self.nbFiles, self.rejectedFiles, self.storageProvided/(1024*1024), self.storageUsed/(1024*1024), self.storageAvailable/(1024*1024)))
        print("|==================================================================================|")
        tracker.storageUsed.append(self.storageUsed/(1024*1024))
        tracker.storageAvailable.append(self.storageAvailable/(1024*1024))
        tracker.nbNodes.append(self.nbNodes)
        tracker.nbFiles.append(self.nbFiles/1000000)

    def snapshot(self):
        print("Creating a snapshot...")
        nodesDict = []
        for node in self.nodes:
            blocksDict = []
            #for block in node.blocks:
            #    blocksDict.append({"fileID" : block.fileID, "blockID" : block.blockID, "size" : block.size})
            nodesDict.append({"nodeID" : node.ID, "storage" : node.storage, "used" : node.used, "available" : node.available, "latency": node.latency, "blocks": blocksDict})

        network = {"Name" : "Codex", "Number of nodes" : self.nbNodes, "nodes" : nodesDict}
        with open(self.name+"/Codex.json", "w") as outfile:
            json.dump(network, outfile)
        print("Snapshot Created.")

    def makeReport(self):
        output = "<html><head><title>Report "+self.name+"</title></head><body>\n"
        output = output+"<h1>"+self.name+"</h1><br/>\n"
        output = output+"<img src='nbNodes.png'><br/>\n"
        output = output+"<img src='nbFiles.png'><br/>\n"
        output = output+"<img src='storage.png'><br/>\n"
        output = output+"<img src='storageNodes.png'><br/>\n"
        output = output+"<img src='fileECN.png'><br/>\n"
        output = output+"<a href='Codex.json'> JSON snapshot </a><br/>\n"
        output = output+"</body></html>"
        with open(self.name+"/index.html", "w") as outfile:
            outfile.write(output)
            outfile.close()
        print("Report html writen.")


    def plotData(self, tracker):
        dir = os.path.join(os.getcwd(), self.name)
        if not os.path.exists(dir):
            os.mkdir(dir)
        used = []
        avai = []
        print("Plotting historic data...")
        self.nodes.sort(key=lambda x: x.used, reverse=True)
        for node in self.nodes:
            used.append(node.used/(1024*1024))
            avai.append(node.available/(1024*1024))
        print("Network is using %f TBs and has %f TBs available" % (self.storageUsed/(1024*1024), self.storageAvailable/(1024*1024)))
        print("Network is using %f TBs and has %f TBs available" % (sum(used), sum(avai)))

        ECNstats = [0] * self.config.defaultECN
        for file in self.files:
            ECNstats[file.ECN-1] = ECNstats[file.ECN-1] + 1
        dECN = []
        lECN = []
        for i in range(len(ECNstats)):
            if ECNstats[i] > 0:
                dECN.append(ECNstats[i])
                lECN.append(i+1)
        print("Network has %i files, %i were treated" % (self.nbFiles, sum(dECN)))

        plotHistoricData(tracker.nbNodes, "Hours", "Nb. of nodes", self.name+"/nbNodes.png")
        plotHistoricData(tracker.nbFiles, "Hours", "Nb. of files (Millions)", self.name+"/nbFiles.png")
        plotStackedBars(2, [tracker.storageUsed, tracker.storageAvailable], ["Used", "Available"], "Hours", "Storage (TBs)", self.name+"/storage.png")
        plotStackedBars(2, [used, avai], ["Used", "Available"], "Nodes", "Storage (TBs)", self.name+"/storageNodes.png")
        plotPieChart(dECN, lECN, self.name+"/fileECN.png")

        self.makeReport()
        self.snapshot()


def run():

    # Initialization
    config = Config()
    network = Network(config)
    tracker = Tracker()

    # Main Loop
    print("Starting simulation %s..." % network.name)
    for sec in range(60*60*24*config.simulationLength): # X days in seconds
        # Adding storage nodes to the network
        if (network.nbNodes < (network.config.minNbNodes)): # Bootstrap a number of nodes
            network.addNode()
        else:
            if ((network.storageUsed * 100 / network.storageProvided) > config.meanUsage): # Only add more storage if X% in use already
                dice = random.random() * 100
                if (dice < (network.storageUsed * 100 / network.storageProvided)): # Less space avilable more likelihood of incoming nodes
                    network.addNode()

        # Uploading files to the network
        if (network.storageProvided - network.storageUsed > network.config.maxFileSize) and (network.nbNodes >= network.config.minNbNodes): # if enough space and enough storage providers
            network.addFile()

        if (sec % 3600 == 0): # Every hour
            network.trackStats(sec, tracker)
    print("Simulation %s finished." % network.name)

    # Plot Data
    # network.plotData(tracker)
    print("Done.")

run()

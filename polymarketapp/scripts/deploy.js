const hre = require("hardhat");

async function main() {
  console.log("Deploying PredictionMarket contract to Sepolia...");

  const PredictionMarket = await hre.ethers.getContractFactory("PredictionMarket");
  const predictionMarket = await PredictionMarket.deploy();

  await predictionMarket.waitForDeployment();
  const address = await predictionMarket.getAddress();

  console.log("\n✅ Contract deployed successfully!");
  console.log("Contract Address:", address);
  console.log("Network: Sepolia Testnet");
  console.log("\n📋 Next steps:");
  console.log("1. Save this address to your .env file as CONTRACT_ADDRESS");
  console.log("2. Verify contract on Etherscan:");
  console.log(`   https://sepolia.etherscan.io/address/${address}`);
  console.log("\n💡 To verify:");
  console.log(`   npx hardhat verify --network sepolia ${address}`);

  return address;
}

main()
  .then((address) => {
    console.log("\n🎉 Deployment complete!");
    process.exit(0);
  })
  .catch((error) => {
    console.error("\n❌ Deployment failed:");
    console.error(error);
    process.exit(1);
  });


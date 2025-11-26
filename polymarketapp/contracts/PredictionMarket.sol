// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title PredictionMarket
 * @dev Simple prediction market contract for creating and resolving markets on-chain
 * Markets are created on-chain, but betting happens off-chain (hybrid approach)
 */
contract PredictionMarket {
    struct Market {
        uint256 id;
        string question;
        string description;
        uint256 endDate;
        address creator;
        MarketStatus status;
        Resolution resolution;
        uint256 createdAt;
    }

    enum MarketStatus { Open, Resolved, Cancelled }
    enum Resolution { None, Yes, No }

    uint256 public marketCount;
    mapping(uint256 => Market) public markets;
    
    event MarketCreated(
        uint256 indexed marketId,
        address indexed creator,
        string question,
        uint256 endDate
    );
    
    event MarketResolved(
        uint256 indexed marketId,
        Resolution resolution
    );

    /**
     * @dev Create a new prediction market
     * @param _question The market question
     * @param _description Additional market description
     * @param _endDate Unix timestamp for market end date
     */
    function createMarket(
        string memory _question,
        string memory _description,
        uint256 _endDate
    ) public returns (uint256) {
        require(bytes(_question).length > 0, "Question cannot be empty");
        require(_endDate > block.timestamp, "End date must be in the future");

        marketCount++;
        uint256 marketId = marketCount;

        markets[marketId] = Market({
            id: marketId,
            question: _question,
            description: _description,
            endDate: _endDate,
            creator: msg.sender,
            status: MarketStatus.Open,
            resolution: Resolution.None,
            createdAt: block.timestamp
        });

        emit MarketCreated(marketId, msg.sender, _question, _endDate);
        return marketId;
    }

    /**
     * @dev Resolve a market (only creator can resolve)
     * @param _marketId The market ID to resolve
     * @param _resolution YES (1) or NO (2)
     */
    function resolveMarket(uint256 _marketId, Resolution _resolution) public {
        require(_marketId > 0 && _marketId <= marketCount, "Invalid market ID");
        Market storage market = markets[_marketId];
        
        require(market.status == MarketStatus.Open, "Market not open");
        require(market.creator == msg.sender, "Only creator can resolve");
        require(block.timestamp >= market.endDate, "Market not yet ended");
        require(_resolution == Resolution.Yes || _resolution == Resolution.No, "Invalid resolution");

        market.status = MarketStatus.Resolved;
        market.resolution = _resolution;

        emit MarketResolved(_marketId, _resolution);
    }

    /**
     * @dev Get market details
     * @param _marketId The market ID
     */
    function getMarket(uint256 _marketId) public view returns (
        uint256 id,
        string memory question,
        string memory description,
        uint256 endDate,
        address creator,
        MarketStatus status,
        Resolution resolution,
        uint256 createdAt
    ) {
        require(_marketId > 0 && _marketId <= marketCount, "Invalid market ID");
        Market memory market = markets[_marketId];
        
        return (
            market.id,
            market.question,
            market.description,
            market.endDate,
            market.creator,
            market.status,
            market.resolution,
            market.createdAt
        );
    }

    /**
     * @dev Get total number of markets
     */
    function getMarketCount() public view returns (uint256) {
        return marketCount;
    }
}


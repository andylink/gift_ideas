import { useState } from 'react'
import SearchBar from './components/SearchBar'
import GiftGrid from './components/GiftGrid'
import axios from 'axios'

function App() {
  const [gifts, setGifts] = useState([])
  const [loading, setLoading] = useState(false)

  const searchGifts = async (query) => {
    try {
      setLoading(true)
      const response = await axios.post('http://localhost:5000/api/find-gifts', {
        description: query
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      if (response.data.success) {
        setGifts(response.data.gifts)
      } else {
        console.error('Error:', response.data.error)
        // You might want to show this error to the user
      }
    } catch (error) {
      console.error('Error fetching gifts:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold text-center mb-8 text-gray-800">
          Gift Finder
        </h1>
        <SearchBar onSearch={searchGifts} />
        {loading ? (
          <div className="text-center mt-8">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto"></div>
          </div>
        ) : (
          <GiftGrid gifts={gifts} />
        )}
      </div>
    </div>
  )
}

export default App
